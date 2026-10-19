import asyncio
import contextlib
import time
from collections.abc import Awaitable, Callable

from agent_hud.protocol import GoneMsg, HelloMsg, ServerMsg, ServerType, Status, StatusMsg, UpsertMsg
from agent_hud.state import BoardState, Delta

type Listener = Callable[[ServerMsg], None]


class Hub:
    """Fans board changes out to canvas tabs and other listeners, and lets the agent wait on them."""

    def __init__(self, state: BoardState, *, project: str) -> None:
        self.state: BoardState = state
        self.project: str = project
        self.viewers: int = 0
        self.waiting: int = 0
        self._listeners: list[Listener] = []
        self._submitted: asyncio.Event = asyncio.Event()
        self._joined: asyncio.Event = asyncio.Event()

    def status(self) -> Status:
        return Status(waiting=self.waiting > 0, pending=self.state.pending, viewers=self.viewers)

    def hello(self) -> HelloMsg:
        elements = list(self.state.elements.values())
        return HelloMsg(t=ServerType.HELLO, project=self.project, elements=elements, status=self.status())

    def listen(self, listener: Listener) -> None:
        self._listeners.append(listener)

    def connect(self, listener: Listener) -> None:
        """Add a canvas tab."""
        self.listen(listener)
        self.viewers += 1
        self._joined.set()
        self._joined = asyncio.Event()
        self._emit_status()

    def disconnect(self, listener: Listener) -> None:
        self._listeners.remove(listener)
        self.viewers -= 1
        self._emit_status()

    def publish(self, delta: Delta) -> None:
        for el_id in delta.gone:
            self._emit(GoneMsg(t=ServerType.GONE, id=el_id))
        for el_id in dict.fromkeys(delta.upserted):
            if (el := self.state.elements.get(el_id)) is not None:
                self._emit(UpsertMsg(t=ServerType.UPSERT, element=el))
        if delta.submitted:
            self._submitted.set()
            self._submitted = asyncio.Event()
        self._emit_status()

    def _emit(self, msg: ServerMsg) -> None:
        for listener in list(self._listeners):
            listener(msg)

    def _emit_status(self) -> None:
        self._emit(StatusMsg(t=ServerType.STATUS, status=self.status()))

    async def wait_for_viewer(self, limit: float) -> bool:
        if self.viewers == 0:
            with contextlib.suppress(TimeoutError):
                async with asyncio.timeout(limit):
                    await self._joined.wait()
        return self.viewers > 0

    async def wait_for_submit(
        self, limit: float, tick: Callable[[float], Awaitable[None]], interval: float = 15.0
    ) -> bool:
        """Block until the user presses Send or `limit` seconds pass; call `tick` every `interval`."""
        start = time.monotonic()
        self.waiting += 1
        self._emit_status()
        try:
            while not self.state.unread_submit():
                remaining = limit - (time.monotonic() - start)
                if remaining <= 0:
                    return False
                event = self._submitted
                try:
                    async with asyncio.timeout(min(interval, remaining)):
                        await event.wait()
                except TimeoutError:
                    await tick(time.monotonic() - start)
            return True
        finally:
            self.waiting -= 1
            self._emit_status()
