import asyncio
from collections.abc import AsyncIterator, Generator
from contextlib import contextmanager
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
    Send,
    TActionId,
    TRef,
    Unreact,
)
from agent_hud.models.board import Board, Thread
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


def snapshot_of(state_file: Path) -> Path:
    """The file next to the state file that holds the board as it was at the start of the state file's actions."""
    return state_file.with_suffix(".json")


def read_of(state_file: Path) -> Path:
    """The file next to the state file that holds how many of its actions an agent has had."""
    return state_file.with_suffix(".read")


def last_on(actions: list[Action], ref: TRef, kinds: tuple[type[React | Unreact | Fill], ...]) -> int:
    """The index of the last action of the kinds on the ref."""
    return max(n for n, action in enumerate(actions) if isinstance(action.body, kinds) and action.body.ref == ref)


def net(actions: list[Action], board: Board) -> list[Action]:
    """
    The actions as a turn carries them, on the board at its start: without the moves and places, with the last of the reactions
    on a part and the last of the fills of a cell, and without those where the turn ends as it began.
    """
    kept: list[Action] = []
    for n, action in enumerate(actions):
        match action.body:
            case Move() | Place() | Send():
                continue
            case React(ref=ref) | Unreact(ref=ref):
                if n != last_on(actions, ref, (React, Unreact)):
                    continue
                reaction = action.body.reaction if isinstance(action.body, React) else None
                if reaction == board.threads.get(ref, Thread()).reactions.get(action.author):
                    continue
            case Fill(ref=ref, value=value):
                if n != last_on(actions, ref, (Fill,)) or value == board.values.get(ref):
                    continue
            case _:
                pass
        kept.append(action)
    return kept


class Hud:
    """
    The board, and the log of the actions that made it; and the agents' monitors.
    With a state file, the log is kept there, after the board that its snapshot file holds, with the agents' read
    position beside it, and compacted on a clear and on shutdown: the snapshot takes the board at the start of the
    oldest turn that an agent has not had, and the log keeps the turns from there.
    """

    def __init__(self, state_file: Path | None = None) -> None:
        self.board = Board()
        self.log = Log()
        self.monitors = 0
        self.working = False
        self._heard: dict[TActionId, Heard] = {}
        self._changed = asyncio.Event()
        self._state_file = state_file
        self._file_start = 0
        self._positions: list[list[int]] = []
        if state_file is not None and snapshot_of(state_file).exists():
            self.board = Board.model_validate_json(snapshot_of(state_file).read_text())
        self._turn_boards: dict[int, Board] = {0: self.board}
        if state_file is not None and state_file.exists():
            with state_file.open() as lines:
                self._take([Action.model_validate_json(line) for line in lines])
        read = int(read_of(state_file).read_text()) if state_file is not None and read_of(state_file).exists() else 0
        self._agent_read = min(read, self._turn_start())

    def act(self, actions: list[Action]) -> None:
        """Apply the actions in order, all or nothing. Misfit, with the index of the action, if one does not fit the board."""
        self._take(actions)
        if self._state_file is None:
            return
        if any(isinstance(action.body, Clear) for action in actions):
            self.compact()
            return
        with self._state_file.open("a") as lines:
            lines.writelines(f"{action.model_dump_json()}\n" for action in actions)

    def compact(self) -> None:
        """
        Write the board at the start of the oldest turn that an agent has not had, or of the user's turn, to the
        snapshot file, the turns from there to the state file, and the read position beside them.
        """
        if self._state_file is None:
            return
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        keep = min(self._agent_read, self._turn_start())
        snapshot = snapshot_of(self._state_file)
        fresh = snapshot.with_name(f"{snapshot.name}.new")
        fresh.write_text(self._turn_boards[keep].model_dump_json())
        fresh.replace(snapshot)
        with self._state_file.open("w") as lines:
            lines.writelines(f"{action.model_dump_json()}\n" for action in self.log.actions[keep:])
        self._file_start = keep
        self._keep_read()

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
        """The user's actions from the turn start to the end, as the agent hears them."""
        actions = [action for action in self.log.actions[start:end] if action.author is Author.user]
        return tuple(self._heard[action.id] for action in net(actions, self._turn_boards[start]))

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
        if self._state_file is not None:
            read_of(self._state_file).write_text(str(self._agent_read - self._file_start))

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
