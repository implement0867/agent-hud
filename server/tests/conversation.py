import asyncio
from collections.abc import AsyncGenerator
from contextlib import AsyncExitStack, asynccontextmanager, suppress
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from fastmcp import Client
from websockets.asyncio.client import ClientConnection, connect

from agent_hud.models.actions import Action, TBody
from agent_hud.models.board import Board
from agent_hud.models.events import Accepted, PageEventAdapter, Rejected, Request, Snapshot
from tests.factories import as_json


@dataclass
class Agent:
    """The agent's side of the board: the MCP tools over HTTP, and a monitor on the URL that listen returns."""

    tools: Client[Any]
    monitor: ClientConnection

    async def write(self, *bodies: TBody) -> None:
        await self.tools.call_tool("write", {"actions": as_json(*bodies)})

    async def hear(self, count: int) -> list[TBody]:
        """The next user actions that the monitor gets, in order. TimeoutError if fewer come in five seconds."""
        async with asyncio.timeout(5):
            return [Action.model_validate_json(await self.monitor.recv()).body for _ in range(count)]

    @asynccontextmanager
    async def listen(self) -> AsyncGenerator[None]:
        """Open a new monitor, as the agent does when its last monitor ended, until the context ends."""
        async with connect((await self.tools.call_tool("listen", {})).data, proxy=None) as self.monitor:
            yield


@dataclass
class User:
    """The user's side of the board: a page on the board websocket, and the board that the page shows."""

    page: ClientConnection
    board: Board

    async def act(self, body: TBody) -> Accepted | Rejected:
        """Ask the board to take the action, as the page does on a click, and take the boards that come before the reply."""
        request = Request(id=uuid4().hex, body=body)
        await self.page.send(request.model_dump_json())
        async with asyncio.timeout(5):
            while True:
                match PageEventAdapter.validate_json(await self.page.recv()):
                    case Snapshot(board=board):
                        self.board = board
                    case Accepted(id=request.id) | Rejected(id=request.id) as answer:
                        return answer
                    case other:
                        raise AssertionError(f"a reply to another request: {other}")

    async def sees(self, board: Board) -> Board:
        """The board that the page shows once it shows the board, or after a second without it."""
        with suppress(TimeoutError):
            async with asyncio.timeout(1):
                while self.board != board:
                    self.board = Snapshot.model_validate_json(await self.page.recv()).board
        return self.board


@asynccontextmanager
async def open_page(address: tuple[str, int]) -> AsyncGenerator[User]:
    """A user on a new page from the app's origin, until the context ends."""
    host, port = address
    async with connect(f"ws://{host}:{port}/ws", origin=f"http://{host}:{port}", proxy=None) as page:
        yield User(page, Snapshot.model_validate_json(await page.recv()).board)


@asynccontextmanager
async def open_agent(address: tuple[str, int]) -> AsyncGenerator[Agent]:
    """An agent that has connected to the MCP server and opened its monitor, until the context ends."""
    host, port = address
    async with AsyncExitStack() as stack:
        tools = await stack.enter_async_context(Client(f"http://{host}:{port}/mcp/"))
        url = (await tools.call_tool("listen", {})).data
        yield Agent(tools, await stack.enter_async_context(connect(url, proxy=None)))
