import asyncio
from collections.abc import AsyncIterator, Generator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from difflib import unified_diff

from agent_hud.models.actions import (
    Action,
    Author,
    Clear,
    Comment,
    Link,
    Misfit,
    Move,
    Place,
    Put,
    Remove,
    Resize,
    Restore,
    Send,
    TActionId,
    TCardId,
)
from agent_hud.models.board import Board
from agent_hud.models.events import AgentState, Edit, EventKind, Heard, Snapshot, Turn
from agent_hud.store import Store


def to_agent_message(board: Board, action: Action) -> Heard:
    """The action as the agent receives it, given the board before it: a put that replaces a card becomes a diff."""
    match action.body:
        case Put(id=card_id, md=md) if card_id in board.cards:
            diff_lines = unified_diff(board.cards[card_id].md.splitlines(), md.splitlines(), lineterm="", n=1)
            body = Edit(kind="edit", id=card_id, diff="\n".join(list(diff_lines)[2:]))
        case _:
            body = action.body
    return Heard(id=action.id, author=action.author, body=body)


def without_layout_actions(actions: list[Action]) -> list[Action]:
    """The actions without moves, resizes, places and sends: a turn does not carry them, and read returns the layout."""
    return [action for action in actions if not isinstance(action.body, Move | Resize | Place | Send)]


@dataclass(frozen=True)
class ChangesSince:
    """What came after an action: the cards that changed, or None when every card counts, and the ids of the actions."""

    cards: set[TCardId] | None
    actions: set[TActionId]


def turn_start(actions: Sequence[Action]) -> int:
    """The index in the actions after the user's last send, or 0."""
    return next((n + 1 for n in range(len(actions) - 1, -1, -1) if actions[n].ends_turn), 0)


def turn_end(actions: Sequence[Action], start: int) -> int | None:
    """The index in the actions after the first send from start on, if there is one."""
    return next((n + 1 for n, action in enumerate(actions[start:], start) if action.ends_turn), None)


def changes_since(actions: Sequence[Action], action_id: TActionId) -> ChangesSince | None:
    """
    What came in the actions after the one with the id: the cards that the actions after it touched, put, removed, restored,
    moved or resized, or with a comment or an arrow on it, or every card when a clear came after it;
    and the ids of those actions. None when the actions do not have the id.
    """
    found = [n for n, action in enumerate(actions) if action.id == action_id]
    if not found:
        return None
    after = actions[found[-1] + 1 :]
    changed: set[TCardId] | None = set()
    for action in after:
        match action.body, changed:
            case Clear(), _:
                changed = None
            case _, None:
                pass
            case (
                (
                    Put(id=card_id)
                    | Remove(id=card_id)
                    | Restore(id=card_id)
                    | Move(id=card_id)
                    | Resize(id=card_id)
                    | Place(id=card_id)
                ),
                _,
            ):
                changed.add(card_id)
            case Comment(card=card_id), _:
                changed.add(card_id)
            case Link(card=card_id, dst=dst), _:
                changed.update((card_id, dst))
            case _:
                pass
    return ChangesSince(changed, {action.id for action in after})


class Exchange:
    """
    The board, the actions that made it, and the agents' monitors, kept in the store.
    ValidationError when the store does not fit this version.
    """

    def __init__(self, store: Store) -> None:
        self.monitors = 0
        self.working = False
        self._heard: dict[TActionId, Heard] = {}
        self._changed = asyncio.Event()
        self._positions: list[list[int]] = []
        self._store = store
        self._base, self.board, actions, read = store.load()
        self.actions: list[Action] = []
        self._turn_boards: dict[int, Board] = {0: self.board}
        self._take(actions)
        self._agent_read = min(read - self._base, turn_start(self.actions))

    def act(self, actions: list[Action]) -> None:
        """Apply the actions in order, all or nothing. Misfit, with the index of the action, if one does not fit the board."""
        start = len(self.actions)
        self._take(actions)
        self._store.append(self._base + start, actions)
        if any(isinstance(action.body, Clear) for action in actions):
            self.compact()

    def compact(self) -> None:
        """
        Make the board at the start of the oldest turn that an agent has not had, or of the user's turn, the checkpoint
        of the store, so that it keeps the turns from there alone.
        """
        keep = min(self._agent_read, turn_start(self.actions))
        self._store.compact(self._base + keep, self._turn_boards[keep], self._base + self._agent_read)

    def close(self) -> None:
        """Let the store go, for another process to hold."""
        self._store.close()

    def snapshot(self) -> Snapshot:
        match self.monitors, self.working:
            case 0, _:
                agent = AgentState.away
            case _, True:
                agent = AgentState.working
            case _:
                agent = AgentState.waiting
        pending = self._turn(turn_start(self.actions), len(self.actions))
        waiting = sum(action.ends_turn for action in self.actions[self._agent_read :])
        return Snapshot(
            kind=EventKind.snapshot,
            board=self.board,
            agent=agent,
            pending=pending,
            unsent=len(pending),
            waiting=waiting,
        )

    async def snapshots(self) -> AsyncIterator[Snapshot]:
        """The snapshot now, then again after each change to the board or to the agents."""
        last = None
        while True:
            changed = self._changed
            if (snapshot := self.snapshot()) != last:
                last = snapshot
                yield snapshot
            await changed.wait()

    @contextmanager
    def monitor(self) -> Generator[None]:
        """Count an agent's monitor as open until the context ends."""
        self.monitors += 1
        self._notify()
        try:
            yield
        finally:
            self.monitors -= 1
            self._notify()

    async def user_turns(self) -> AsyncIterator[Turn]:
        """
        The user's turns that no agent has had, then each new one, without the sends that end them.
        A turn counts as had once the agent asks for the next, so a turn whose send fails goes to the next monitor.
        """
        position = [self._agent_read]
        self._positions.append(position)
        try:
            while True:
                changed = self._changed
                while (end := turn_end(self.actions, position[0])) is not None:
                    turn = Turn.of(self.actions[end - 1].id, self._turn(position[0], end))
                    position[0] = end
                    if not self.working:
                        self.working = True
                        self._notify()
                    yield turn
                    self._mark_read(end)
                await changed.wait()
        finally:
            self._positions.remove(position)

    def _turn(self, start: int, end: int) -> tuple[Heard, ...]:
        """
        The user's actions from the turn start to the end, as the agent hears them.
        """
        actions = [action for action in self.actions[start:end] if action.author is Author.user]
        return tuple(self._heard[action.id] for action in without_layout_actions(actions))

    def _mark_read(self, end: int) -> None:
        if end <= self._agent_read:
            return
        self._agent_read = end
        self._forget_boards()
        self._store.keep_read(self._base + self._agent_read)
        self._notify()

    def _forget_boards(self) -> None:
        """Drop the boards at the starts of the turns that every monitor has had and that the user's turn is past."""
        floor = min([self._agent_read, turn_start(self.actions), *(position[0] for position in self._positions)])
        for start in [start for start in self._turn_boards if start < floor]:
            del self._turn_boards[start]

    def _take(self, actions: list[Action]) -> None:
        boards = [self.board]
        for n, action in enumerate(actions, start=1):
            try:
                boards.append(boards[-1].apply(action))
            except ValueError as error:
                raise Misfit(n, action.body.kind, str(error)) from error
        self._heard |= {
            action.id: to_agent_message(board, action)
            for action, board in zip(actions, boards[:-1], strict=True)
            if action.author is Author.user
        }
        self.board = boards[-1]
        offset = len(self.actions)
        for n, action in enumerate(actions, start=1):
            if action.ends_turn:
                self._turn_boards[offset + n] = boards[n]
        self.actions.extend(actions)
        if any(action.author is Author.agent for action in actions):
            self.working = False
        self._notify()

    def _notify(self) -> None:
        self._changed.set()
        self._changed = asyncio.Event()
