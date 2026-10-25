import asyncio
from collections.abc import AsyncIterator, Generator
from contextlib import contextmanager, suppress
from difflib import unified_diff
from pathlib import Path

from agent_hud.log import Log
from agent_hud.models.actions import (
    Action,
    Author,
    Clear,
    Fill,
    Misfit,
    Move,
    Place,
    Put,
    React,
    Resize,
    Send,
    TActionId,
    TBody,
    TRef,
    Unreact,
)
from agent_hud.models.board import Board, Thread
from agent_hud.models.events import AgentState, Edit, EventKind, Heard, Snapshot, Turn
from agent_hud.store import Store


def hear(board: Board, action: Action) -> Heard:
    """The action as the agent hears it on the board before it: a put on a card of the board as a diff, and the text of the parts it names."""
    match action.body:
        case Put(id=card_id, md=md) if card_id in board.cards:
            lines = unified_diff(board.cards[card_id].md.splitlines(), md.splitlines(), lineterm="", n=1)
            body = Edit(kind="edit", id=card_id, diff="\n".join(list(lines)[2:]))
        case _:
            body = action.body
    return Heard(id=action.id, author=action.author, body=body, parts=board.part_texts(action.body))


def setting(body: TBody) -> tuple[str, TRef] | None:
    """What the action sets, which a later action that sets the same replaces: the reaction on a ref, or a cell's value."""
    match body:
        case React(ref=ref) | Unreact(ref=ref):
            return "reaction", ref
        case Fill(ref=ref):
            return "value", ref
        case _:
            return None


def net(actions: list[Action], board: Board) -> list[Action]:
    """
    The actions as a turn carries them, on the board at its start: without the moves, resizes and places, with the last of
    the reactions on a part and the last of the fills of a cell, and without those where the turn ends as it began.
    """
    last = {key: n for n, action in enumerate(actions) if (key := setting(action.body)) is not None}

    def carries(n: int, action: Action) -> bool:
        if (key := setting(action.body)) is not None and last[key] != n:
            return False
        match action.body:
            case Move() | Resize() | Place() | Send():
                return False
            case React(ref=ref, reaction=reaction):
                return reaction != board.threads.get(ref, Thread()).reactions.get(action.author)
            case Unreact(ref=ref):
                return action.author in board.threads.get(ref, Thread()).reactions
            case Fill(ref=ref, value=value):
                return value != board.values.get(ref)
            case _:
                return True

    return [action for n, action in enumerate(actions) if carries(n, action)]


class Hud:
    """
    The board, and the log of the actions that made it; and the agents' monitors.
    With a state file, the log is kept there after the board at a checkpoint, with the agents' read position, and
    compacted on a clear and on shutdown: the checkpoint takes the board at the start of the oldest turn that an agent
    has not had, and the file keeps the turns from there. One process holds the state file: RuntimeError when another does.
    """

    def __init__(self, state_file: Path | None = None) -> None:
        self.board = Board()
        self.log = Log()
        self.monitors = 0
        self.working = False
        self._heard: dict[TActionId, Heard] = {}
        self._changed = asyncio.Event()
        self._positions: list[list[int]] = []
        self._store = None if state_file is None else Store(state_file)
        # The sequence number in the store of the first action of the log.
        self._base = 0
        self._agent_read = 0
        self._turn_boards: dict[int, Board] = {0: self.board}
        if self._store is not None:
            self._base, self.board, actions, read = self._store.load()
            self._turn_boards = {0: self.board}
            self._take(actions)
            self._agent_read = min(read - self._base, self._turn_start())

    def act(self, actions: list[Action]) -> None:
        """Apply the actions in order, all or nothing. Misfit, with the index of the action, if one does not fit the board."""
        start = len(self.log.actions)
        self._take(actions)
        if self._store is None:
            return
        self._store.append(self._base + start, actions)
        if any(isinstance(action.body, Clear) for action in actions):
            self.compact()

    def compact(self) -> None:
        """
        Make the board at the start of the oldest turn that an agent has not had, or of the user's turn, the checkpoint
        of the state file, so that it keeps the turns from there alone.
        """
        if self._store is None:
            return
        keep = min(self._agent_read, self._turn_start())
        self._store.compact(self._base + keep, self._turn_boards[keep], self._base + self._agent_read)

    def close(self) -> None:
        """Let the state file go, for another process to hold."""
        if self._store is not None:
            self._store.close()

    def snapshot(self) -> Snapshot:
        match self.monitors, self.working:
            case 0, _:
                agent = AgentState.away
            case _, True:
                agent = AgentState.working
            case _:
                agent = AgentState.waiting
        pending = self._turn(self._turn_start(), len(self.log.actions))
        waiting = sum(action.ends_turn for action in self.log.actions[self._agent_read :])
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
            async for _ in self.log.follow(position[0]):
                while (end := self._turn_end(position[0])) is not None:
                    turn = Turn(actions=self._turn(position[0], end))
                    position[0] = end
                    if not self.working:
                        self.working = True
                        self._notify()
                    yield turn
                    self._mark_read(end)
        finally:
            self._positions.remove(position)

    def _turn(self, start: int, end: int) -> tuple[Heard, ...]:
        """
        The user's actions from the turn start to the end, as the agent hears them: the net against the board at the
        turn's start with the agent's actions of the turn applied, so that a value the user sets on a row that the agent
        put in the turn counts, even when the row that had that number before carried the same value.
        """
        window = self.log.actions[start:end]
        base = self._turn_boards[start]
        for action in window:
            if action.author is not Author.agent:
                continue
            # An agent action on what the user made in the turn, such as a reaction on the user's note, does not fit
            # the board without the user's actions; the net then compares against the board without it, which carries
            # the user's actions on it.
            with suppress(ValueError):
                base = base.apply(action)
        actions = [action for action in window if action.author is Author.user]
        return tuple(self._heard[action.id] for action in net(actions, base))

    def _mark_read(self, end: int) -> None:
        if end <= self._agent_read:
            return
        self._agent_read = end
        self._forget_boards()
        self._keep_read()
        self._notify()

    def _forget_boards(self) -> None:
        """Drop the boards at the starts of the turns that every monitor has had and that the user's turn is past."""
        floor = min([self._agent_read, self._turn_start(), *(position[0] for position in self._positions)])
        for start in [start for start in self._turn_boards if start < floor]:
            del self._turn_boards[start]

    def _keep_read(self) -> None:
        if self._store is not None:
            self._store.keep_read(self._base + self._agent_read)

    def _take(self, actions: list[Action]) -> None:
        boards = [self.board]
        for n, action in enumerate(actions, start=1):
            try:
                boards.append(boards[-1].apply(action))
            except ValueError as error:
                raise Misfit(n, action.body.kind, str(error)) from error
        self._heard |= {
            action.id: hear(board, action)
            for action, board in zip(actions, boards[:-1], strict=True)
            if action.author is Author.user
        }
        self.board = boards[-1]
        offset = len(self.log.actions)
        for n, action in enumerate(actions, start=1):
            if action.ends_turn:
                self._turn_boards[offset + n] = boards[n]
        self.log.extend(actions)
        if any(action.author is Author.agent for action in actions):
            self.working = False
        self._notify()

    def _turn_start(self) -> int:
        """The index in the log after the user's last send, or 0."""
        actions = self.log.actions
        return next((n + 1 for n in range(len(actions) - 1, -1, -1) if actions[n].ends_turn), 0)

    def _turn_end(self, start: int) -> int | None:
        """The index in the log after the first send from start on, if there is one."""
        return next((n + 1 for n, action in enumerate(self.log.actions[start:], start) if action.ends_turn), None)

    def _notify(self) -> None:
        self._changed.set()
        self._changed = asyncio.Event()
