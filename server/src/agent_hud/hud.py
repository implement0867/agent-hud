import asyncio
from collections.abc import AsyncIterator, Generator
from contextlib import contextmanager
from difflib import unified_diff
from pathlib import Path

from agent_hud.log import Log
from agent_hud.models.actions import Action, ActionKind, Author, Misfit, Put, TActionId
from agent_hud.models.board import Board
from agent_hud.models.events import AgentState, Edit, EventKind, Heard, Snapshot, Turn


def hear(board: Board, action: Action) -> Heard:
    """The action as the agent hears it on the board before it: a put on a card of the board as a diff, and the text of the parts it names."""
    match action.body:
        case Put(id=card_id, md=md) if card_id in board.cards:
            lines = unified_diff(board.cards[card_id].md.splitlines(), md.splitlines(), lineterm="", n=1)
            body = Edit(kind="edit", id=card_id, diff="\n".join(list(lines)[2:]))
        case _:
            body = action.body
    return Heard(id=action.id, author=action.author, body=body, parts=board.part_texts(action.body))


class Hud:
    """The board, and the log of the actions that made it, kept in the state file if there is one; and the agents' monitors."""

    def __init__(self, state_file: Path | None = None) -> None:
        self.board = Board()
        self.log = Log()
        self.monitors = 0
        self.working = False
        self._heard: dict[TActionId, Heard] = {}
        self._changed = asyncio.Event()
        self._state_file = state_file
        if state_file is not None and state_file.exists():
            with state_file.open() as lines:
                self._take([Action.model_validate_json(line) for line in lines])
        self._agent_read = self._turn_start()

    def act(self, actions: list[Action]) -> None:
        """Apply the actions in order, all or nothing. Misfit, with the index of the action, if one does not fit the board."""
        self._take(actions)
        if self._state_file is not None:
            with self._state_file.open("a") as lines:
                lines.writelines(f"{action.model_dump_json()}\n" for action in actions)

    def snapshot(self) -> Snapshot:
        match self.monitors, self.working:
            case 0, _:
                agent = AgentState.away
            case _, True:
                agent = AgentState.working
            case _:
                agent = AgentState.waiting
        unsent = sum(
            action.author is Author.user and action.body.kind is not ActionKind.move
            for action in self.log.actions[self._turn_start() :]
        )
        return Snapshot(kind=EventKind.snapshot, board=self.board, agent=agent, unsent=unsent)

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
        """The user's turns that no agent has had, then each new one, without the sends that end them."""
        start = self._agent_read
        async for _ in self.log.follow(start):
            while (end := self._turn_end(start)) is not None:
                turn = Turn(
                    actions=tuple(
                        self._heard[action.id]
                        for action in self.log.actions[start:end]
                        if action.author is Author.user and action.body.kind is not ActionKind.send
                    )
                )
                start = end
                self._agent_read = max(self._agent_read, end)
                if not self.working:
                    self.working = True
                    self._notify()
                yield turn

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
