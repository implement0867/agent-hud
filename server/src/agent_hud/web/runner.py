import asyncio
import contextlib
import logging
import os
import socket
import time
from collections.abc import Generator

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


def _try_bind(host: str, port: int) -> socket.socket | None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if os.name == "posix":
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind((host, port))
    except OSError:
        sock.close()
        return None
    sock.listen(64)
    return sock


def bind(host: str, port: int) -> socket.socket:
    """Bind the preferred port, or any free port when it is taken."""
    sock = _try_bind(host, port) or _try_bind(host, 0)
    if sock is None:
        raise OSError(f"cannot bind {host}")
    return sock


class CanvasServer:
    def __init__(self, hub: Hub, settings: HudSettings, *, debug_api: bool = False) -> None:
        self.hub: Hub = hub
        self.settings: HudSettings = settings
        self.debug_api: bool = debug_api
        self.url: str | None = None
        self._server: _EmbeddedServer | None = None
        self._task: asyncio.Task[None] | None = None
        self._opened_at: float | None = None
        self._hinted_at: float | None = None

    async def ensure_started(self) -> str:
        if self._task is None:
            sock = bind(self.settings.host, self.settings.port)
            self.url = f"http://{self.settings.host}:{sock.getsockname()[1]}/"
            config = uvicorn.Config(
                create_app(self.hub, self.settings, debug_api=self.debug_api),
                log_config=None,
                access_log=False,
                lifespan="off",
                log_level="warning",
                timeout_graceful_shutdown=2,
            )
            self._server = _EmbeddedServer(config)
            self._task = asyncio.create_task(self._server.serve(sockets=[sock]))
            log.info("canvas at %s", self.url)
        return self.url or ""

    async def viewer_hint(self) -> str:
        """Open the canvas when no tab shows it. Say so to the agent at most every five minutes."""
        url = await self.ensure_started()
        now = time.monotonic()
        if self.hub.viewers > 0:
            return ""
        if self.settings.open_browser and (self._opened_at is None or now - self._opened_at > 60) and open_browser(url):
            self._opened_at = self._hinted_at = now
            return f"\n(opened {url} in the browser)"
        if self._hinted_at is not None and now - self._hinted_at < 300:
            return ""
        self._hinted_at = now
        return f"\n(no canvas tab is open: ask the user to open {url})"

    async def stop(self) -> None:
        if self._server is not None and self._task is not None:
            self._server.should_exit = True
            await self._task
            self._server = self._task = None

    async def serve_forever(self) -> None:
        await self.ensure_started()
        if self._task is not None:
            await self._task
