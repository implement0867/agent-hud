import asyncio
from collections.abc import AsyncIterator, Generator
from contextlib import contextmanager

from sqlalchemy.orm import Session

from agent_hud.boards import BoardSummary, TBoardName, summarize_board
from agent_hud.models.actions import Action, Author, TActionId
from agent_hud.models.events import AgentState, EventKind, Snapshot, Turn
from agent_hud.models.state import BoardState
from agent_hud.queries.boards import commit_board_state, list_board_names, load_board_state


class Monitor:
    """An agent's open monitor, and the ids of the turns delivered to it."""

    def __init__(self) -> None:
        self.delivered: set[TActionId] = set()


class Exchange:
    """What lives only while the app runs for a board: the agents' open monitors, whether an agent works, and the change events."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.working = False
        self._monitors: list[Monitor] = []
        self._changed = asyncio.Event()

    @property
    def monitors(self) -> int:
        return len(self._monitors)

    def find_agent_state(self) -> AgentState:
        """Find whether an agent is away, works, or waits for the user's turn."""
        match self.monitors, self.working:
            case 0, _:
                return AgentState.away
            case _, True:
                return AgentState.working
            case _:
                return AgentState.waiting

    def take_snapshot(self, state: BoardState) -> Snapshot:
        """Take the board and the agent's state, for the page."""
        return Snapshot(
            kind=EventKind.snapshot,
            board=state.board,
            agent=self.find_agent_state(),
            pending=state.open_turn,
            unsent=len(state.open_turn),
            waiting=len(state.sent_turns),
        )

    @contextmanager
    def open_monitor(self) -> Generator[Monitor]:
        """Open an agent's monitor until the context ends."""
        monitor = Monitor()
        self._monitors.append(monitor)
        self.notify_change()
        try:
            yield monitor
        finally:
            self._monitors.remove(monitor)
            self.notify_change()

    def mark_delivered(self, monitor: Monitor, turn: Turn) -> None:
        """Mark the turn as delivered to the monitor, so that the agent works on it."""
        monitor.delivered.add(turn.id)
        self.working = True
        self.notify_change()

    def find_turns_delivered_to_all(self, state: BoardState) -> set[TActionId]:
        """Find the ids of the sent turns delivered to every open monitor."""
        return {turn.id for turn in state.sent_turns if all(turn.id in each.delivered for each in self._monitors)}

    def notify_change(self) -> None:
        """Wake each watcher of the board, after a change to the board or to the agents."""
        self._changed.set()
        self._changed = asyncio.Event()

    async def watch_changes(self) -> AsyncIterator[None]:
        """Yield now, then again after each change to the board or to the agents."""
        while True:
            changed = self._changed
            yield
            await changed.wait()


def act_on_board(session: Session, exchange: Exchange, actions: list[Action]) -> tuple[BoardState, BoardState]:
    """
    Apply the actions to the board's state, commit the new state, and wake the board's watchers.
    Return the state before and after. Misfit, with the index of the action, if one does not fit the board.
    """
    before = load_board_state(session, exchange.name)
    after = before.apply_actions(actions)
    commit_board_state(session, exchange.name, after)
    if any(action.author is Author.agent for action in actions):
        exchange.working = False
    exchange.notify_change()
    return before, after


def summarize_boards(session: Session, exchanges: dict[TBoardName, Exchange]) -> list[BoardSummary]:
    """Summarize each board in the database, with the agent state of its live exchange, or away when it has none."""
    return [
        summarize_board(
            name,
            load_board_state(session, name),
            exchanges[name].find_agent_state() if name in exchanges else AgentState.away,
        )
        for name in list_board_names(session)
    ]
