import asyncio
from collections.abc import AsyncIterator, Generator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import assert_never

from agent_hud.models.actions import TActionId
from agent_hud.models.events import AgentState, Turn


@dataclass(eq=False)
class Monitor:
    """An agent's open monitor, and the ids of the turns delivered to it."""

    delivered: set[TActionId] = field(default_factory=set)


@dataclass(frozen=True)
class Away:
    """No monitor is open."""


@dataclass(frozen=True)
class Waiting:
    """Monitors are open, and the agent waits for the user's next turn."""

    monitors: list[Monitor]


@dataclass(frozen=True)
class Working:
    """Monitors are open, and one has the user's last turn, which the agent has not answered."""

    monitors: list[Monitor]


type TAgent = Away | Waiting | Working


class Presence:
    """
    What lives only while the app runs, for one board: the agent, with its monitors, and an event that wakes the
    board's watchers after each change to the board or to the agent.
    """

    def __init__(self) -> None:
        self.agent: TAgent = Away()
        self.changed = asyncio.Event()

    @property
    def monitors(self) -> list[Monitor]:
        match self.agent:
            case Away():
                return []
            case Waiting(monitors) | Working(monitors):
                return monitors
            case _:
                assert_never(self.agent)

    @property
    def agent_state(self) -> AgentState:
        match self.agent:
            case Away():
                return AgentState.away
            case Waiting():
                return AgentState.waiting
            case Working():
                return AgentState.working
            case _:
                assert_never(self.agent)

    @contextmanager
    def open_monitor(self) -> Generator[Monitor]:
        """Open an agent's monitor until the context ends; the agent waits when it was away."""
        monitor = Monitor()
        match self.agent:
            case Away():
                self.agent = Waiting([monitor])
            case Waiting(monitors) | Working(monitors):
                monitors.append(monitor)
            case _:
                assert_never(self.agent)
        self.notify_change()
        try:
            yield monitor
        finally:
            self.close_monitor(monitor)

    def close_monitor(self, monitor: Monitor) -> None:
        """Close the monitor; the agent is away once no monitor is open."""
        match self.agent:
            case Waiting(monitors) | Working(monitors):
                monitors.remove(monitor)
                if not monitors:
                    self.agent = Away()
            case Away():
                raise RuntimeError("no monitor is open")
            case _:
                assert_never(self.agent)
        self.notify_change()

    def mark_delivered(self, monitor: Monitor, turn: Turn) -> None:
        """Mark the turn delivered to the monitor: the agent works on it until it writes."""
        monitor.delivered.add(turn.id)
        match self.agent:
            case Waiting(monitors) | Working(monitors):
                self.agent = Working(monitors)
            case Away():
                raise RuntimeError("no monitor is open")
            case _:
                assert_never(self.agent)
        self.notify_change()

    def note_agent_wrote(self) -> None:
        """The agent answered the turn it worked on, so it waits for the next."""
        match self.agent:
            case Working(monitors):
                self.agent = Waiting(monitors)
            case Away() | Waiting():
                pass
            case _:
                assert_never(self.agent)

    def find_turns_delivered_to_all(self, turns: Sequence[Turn]) -> set[TActionId]:
        """The ids of the turns that every open monitor has."""
        return {turn.id for turn in turns if all(turn.id in monitor.delivered for monitor in self.monitors)}

    def notify_change(self) -> None:
        """Wake each watcher of the board."""
        self.changed.set()
        self.changed = asyncio.Event()

    async def watch_changes(self) -> AsyncIterator[None]:
        """Yield now, then again after each change to the board or to the agent."""
        while True:
            changed = self.changed
            yield
            await changed.wait()
