import asyncio
import socket
from collections.abc import AsyncGenerator, Callable
from contextlib import AsyncExitStack, asynccontextmanager, suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
import uvicorn
from fastmcp import Client
from websockets.asyncio.client import ClientConnection, connect

from agent_hud.models.actions import TBody
from agent_hud.models.board import Board
from agent_hud.models.events import Accepted, PageEventAdapter, Rejected, Request, Snapshot, THeardBody, Turn
from agent_hud.settings import get_settings
from agent_hud.web import create_app
from tests.factories import as_json, send


@dataclass
class Agent:
    """The agent's side of the board: the MCP tools over HTTP, and a monitor on the URL that listen returns."""

    tools: Client[Any]
    monitor: ClientConnection

    async def write(self, *bodies: TBody) -> None:
        await self.tools.call_tool("write", {"actions": as_json(*bodies)})

    async def turn(self) -> Turn:
        """The next turn of the user that the monitor gets. TimeoutError if none comes in five seconds."""
        async with asyncio.timeout(5):
            return Turn.model_validate_json(await self.monitor.recv())

    async def hear(self) -> list[THeardBody]:
        """The user's actions in the next turn that the monitor gets, in order."""
        return [heard.body for heard in (await self.turn()).actions]

    @asynccontextmanager
    async def listen(self) -> AsyncGenerator[None]:
        """Open a new monitor, as the agent does when its last monitor ended, until the context ends."""
        async with connect((await self.tools.call_tool("listen", {})).data, proxy=None) as self.monitor:
            yield


@dataclass
class User:
    """The user's side of the board: a page on the board websocket, and the last snapshot that the page got."""

    page: ClientConnection
    snapshot: Snapshot

    @property
    def board(self) -> Board:
        return self.snapshot.board

    async def act(self, body: TBody) -> Accepted | Rejected:
        """Ask the board to take the action, as the page does on a click, and take the boards that come before the reply."""
        request = Request(id=uuid4().hex, body=body)
        await self.page.send(request.model_dump_json())
        async with asyncio.timeout(5):
            while True:
                match PageEventAdapter.validate_json(await self.page.recv()):
                    case Snapshot() as snapshot:
                        self.snapshot = snapshot
                    case Accepted(id=request.id) | Rejected(id=request.id) as answer:
                        return answer
                    case other:
                        raise AssertionError(f"a reply to another request: {other}")

    async def send(self) -> None:
        """End the turn, as the page's Send button does."""
        assert isinstance(await self.act(send()), Accepted)

    async def notes(self, check: Callable[[Snapshot], bool]) -> Snapshot:
        """The first snapshot that passes the check, or the last one after a second without it."""
        with suppress(TimeoutError):
            async with asyncio.timeout(1):
                while not check(self.snapshot):
                    self.snapshot = Snapshot.model_validate_json(await self.page.recv())
        return self.snapshot

    async def sees(self, board: Board) -> Board:
        """The board that the page shows once it shows the board, or after a second without it."""
        return (await self.notes(lambda snapshot: snapshot.board == board)).board


@asynccontextmanager
async def open_page(address: tuple[str, int]) -> AsyncGenerator[User]:
    """A user on a new page from the app's origin, until the context ends."""
    host, port = address
    async with connect(f"ws://{host}:{port}/ws", origin=f"http://{host}:{port}", proxy=None) as page:
        yield User(page, Snapshot.model_validate_json(await page.recv()))


@asynccontextmanager
async def open_agent(address: tuple[str, int]) -> AsyncGenerator[Agent]:
    """An agent that has connected to the MCP server and opened its monitor, until the context ends."""
    host, port = address
    async with AsyncExitStack() as stack:
        tools = await stack.enter_async_context(Client(f"http://{host}:{port}/mcp/"))
        url = (await tools.call_tool("listen", {})).data
        yield Agent(tools, await stack.enter_async_context(connect(url, proxy=None)))


@asynccontextmanager
async def serve(static_dir: Path) -> AsyncGenerator[tuple[str, int]]:
    """Host and port of the app with the UI in static_dir, on a free port, until the context ends."""
    with pytest.MonkeyPatch.context() as env:
        env.setenv("AGENT_HUD_STATIC_DIR", str(static_dir))
        get_settings.cache_clear()
        app = create_app()
    get_settings.cache_clear()
    # With IPPROTO_TCP, asyncio turns off Nagle's algorithm on each connection, as for the socket uvicorn binds itself.
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
    sock.bind(("127.0.0.1", 0))
    sock.listen()
    server = uvicorn.Server(uvicorn.Config(app, log_config=None))
    task = asyncio.create_task(server.serve(sockets=[sock]))
    try:
        yield sock.getsockname()
    finally:
        server.should_exit = True
        await task
