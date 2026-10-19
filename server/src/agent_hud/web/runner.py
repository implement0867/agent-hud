"""Runs the canvas app inside the host's event loop, on a loopback port."""

import asyncio
import contextlib
import logging
import os
import socket
from collections.abc import Generator

import uvicorn

from agent_hud.board import Board
from agent_hud.settings import HudSettings
from agent_hud.web.app import create_app

log = logging.getLogger(__name__)


class _EmbeddedServer(uvicorn.Server):
    """Uvicorn that leaves signal handling to the host process."""

    @contextlib.contextmanager
    def capture_signals(self) -> Generator[None]:
        yield


def bind(host: str, port: int) -> socket.socket:
    """Bind the preferred port, or any free port when it is taken."""
    for candidate in dict.fromkeys((port, 0)):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if os.name == "posix":
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, candidate))
        except OSError:
            sock.close()
            if candidate == 0:
                raise
            continue
        sock.listen(64)
        return sock
    raise OSError("no port available")


class CanvasServer:
    def __init__(self, board: Board, settings: HudSettings, *, debug_api: bool = False) -> None:
        self.board: Board = board
        self.settings: HudSettings = settings
        self.debug_api: bool = debug_api
        self.port: int | None = None
        self._server: _EmbeddedServer | None = None
        self._task: asyncio.Task[None] | None = None

    async def ensure_started(self) -> str:
        """Start serving on first use; returns the canvas URL."""
        if self._task is None:
            sock = bind(self.settings.host, self.settings.port)
            self.port = int(sock.getsockname()[1])
            config = uvicorn.Config(
                create_app(self.board, self.settings, debug_api=self.debug_api),
                log_config=None,
                access_log=False,
                lifespan="off",
                log_level="warning",
                timeout_graceful_shutdown=2,
            )
            self._server = _EmbeddedServer(config)
            self._task = asyncio.create_task(self._server.serve(sockets=[sock]))
            log.info("canvas at http://%s:%s/", self.settings.host, self.port)
        return f"http://{self.settings.host}:{self.port}/"

    async def stop(self) -> None:
        if self._server is not None and self._task is not None:
            self._server.should_exit = True
            await self._task
            self._server = self._task = None

    async def serve_forever(self) -> None:
        await self.ensure_started()
        if self._task is not None:
            await self._task
