import asyncio
import contextlib
import logging
import math
import os
import socket
import time
from collections.abc import Generator
from dataclasses import dataclass

import uvicorn

from agent_hud.browser import open_browser
from agent_hud.hub import Hub
from agent_hud.settings import HudSettings
from agent_hud.web.app import create_app

log = logging.getLogger(__name__)


class _EmbeddedServer(uvicorn.Server):
    """Uvicorn that leaves signal handling to the host process."""

    @contextlib.contextmanager
    def capture_signals(self) -> Generator[None]:
        yield


def _listen(host: str, port: int) -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if os.name == "posix":
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind((host, port))
    except OSError:
        sock.close()
        raise
    sock.listen(64)
    return sock


def bind(host: str, port: int) -> socket.socket:
    """Bind the preferred port, or any free port when it is taken."""
    try:
        return _listen(host, port)
    except OSError:
        return _listen(host, 0)


@dataclass(frozen=True, slots=True)
class Running:
    server: _EmbeddedServer
    task: asyncio.Task[None]
    url: str


class CanvasServer:
    def __init__(self, hub: Hub, settings: HudSettings, *, debug_api: bool = False) -> None:
        self.hub: Hub = hub
        self.settings: HudSettings = settings
        self.debug_api: bool = debug_api
        self._running: Running | None = None
        self._opened_at: float = -math.inf
        self._hinted_at: float = -math.inf

    async def start(self) -> Running:
        """Start the canvas server once; later calls return the running server."""
        match self._running:
            case Running() as running:
                return running
            case None:
                sock = bind(self.settings.host, self.settings.port)
                config = uvicorn.Config(
                    create_app(self.hub, self.settings, debug_api=self.debug_api),
                    log_config=None,
                    access_log=False,
                    lifespan="off",
                    log_level="warning",
                    timeout_graceful_shutdown=2,
                )
                server = _EmbeddedServer(config)
                url = f"http://{self.settings.host}:{sock.getsockname()[1]}/"
                self._running = Running(server, asyncio.create_task(server.serve(sockets=[sock])), url)
                log.info("canvas at %s", url)
                return self._running

    async def viewer_hint(self) -> str:
        """Open the canvas when no tab shows it. Say so to the agent at most every five minutes."""
        url = (await self.start()).url
        now = time.monotonic()
        if self.hub.viewers > 0:
            return ""
        if self.settings.open_browser and now - self._opened_at > 60 and open_browser(url):
            self._opened_at = self._hinted_at = now
            return f"\n(opened {url} in the browser)"
        if now - self._hinted_at < 300:
            return ""
        self._hinted_at = now
        return f"\n(no canvas tab is open: ask the user to open {url})"

    async def stop(self) -> None:
        match self._running:
            case Running(server=server, task=task):
                server.should_exit = True
                await task
                self._running = None
            case None:
                pass
