import asyncio
from collections.abc import AsyncIterator, Generator
from contextlib import contextmanager

from agent_hud.models.actions import Action, Author, Misfit, TActionId, TCardId
from agent_hud.models.board import Board
from agent_hud.models.events import AgentState, EventKind, Snapshot, Turn
from agent_hud.models.state import BoardState


class Monitor:
    """An agent's open monitor, and the ids of the turns delivered to it."""

    def __init__(self) -> None:
        self.delivered: set[TActionId] = set()


class Exchange:
    """A board's state, and what lives only while the app runs: the agents' open monitors and whether an agent works."""

    def __init__(self, name: str, state: BoardState) -> None:
        self.name = name
        self.state = state
        self.working = False
        self._monitors: list[Monitor] = []
        self._changed = asyncio.Event()

    @property
    def board(self) -> Board:
        return self.state.board

    @property
    def monitors(self) -> int:
        return len(self._monitors)

    def act(self, actions: list[Action]) -> None:
        """Apply the actions in order, all or nothing. Misfit, with the index of the action, if one does not fit the board."""
        state = self.state
        for n, action in enumerate(actions, start=1):
            try:
                state = state.apply_action(action)
            except ValueError as error:
                raise Misfit(n, action.body.kind, str(error)) from error
        self.state = state
        if any(action.author is Author.agent for action in actions):
            self.working = False
        self._notify()

    def mark_read(self, cards: frozenset[TCardId]) -> None:
        """Mark the cards and every message as read by the agent."""
        self.state = self.state.mark_read(cards)

    def mark_delivered(self, monitor: Monitor, turn: Turn) -> None:
        """
        Mark the turn as delivered to the monitor, so that the agent works on it; remove each sent turn that was
        delivered to every open monitor.
        """
        monitor.delivered.add(turn.id)
        delivered_to_all = {
            sent.id for sent in self.state.sent_turns if all(sent.id in each.delivered for each in self._monitors)
        }
        self.state = self.state.remove_turns(delivered_to_all)
        self.working = True
        self._notify()

    def find_agent_state(self) -> AgentState:
        """Find whether an agent is away, works, or waits for the user's turn."""
        match self.monitors, self.working:
            case 0, _:
                return AgentState.away
            case _, True:
                return AgentState.working
            case _:
                return AgentState.waiting

    def take_snapshot(self) -> Snapshot:
        """Take the board and the agent's state, for the page."""
        return Snapshot(
            kind=EventKind.snapshot,
            board=self.board,
            agent=self.find_agent_state(),
            pending=self.state.open_turn,
            unsent=len(self.state.open_turn),
            waiting=len(self.state.sent_turns),
        )

    async def snapshots(self) -> AsyncIterator[Snapshot]:
        """The snapshot now, then again after each change to the board or to the agents."""
        last = None
        while True:
            changed = self._changed
            if (snapshot := self.take_snapshot()) != last:
                last = snapshot
                yield snapshot
            await changed.wait()

    @contextmanager
    def open_monitor(self) -> Generator[Monitor]:
        """Open an agent's monitor until the context ends."""
        monitor = Monitor()
        self._monitors.append(monitor)
        self._notify()
        try:
            yield monitor
        finally:
            self._monitors.remove(monitor)
            self._notify()

    async def wait_for_turns(self, monitor: Monitor) -> AsyncIterator[Turn]:
        """Wait for each sent turn not yet delivered to the monitor, oldest first; a turn comes again until it is marked delivered."""
        while True:
            changed = self._changed
            if undelivered := [turn for turn in self.state.sent_turns if turn.id not in monitor.delivered]:
                yield undelivered[0]
            else:
                await changed.wait()

    def _notify(self) -> None:
        self._changed.set()
        self._changed = asyncio.Event()
