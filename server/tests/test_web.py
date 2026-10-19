import asyncio
import socket
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import uvicorn
from fastmcp import Client
from websockets.asyncio.client import connect
from websockets.exceptions import InvalidStatus

from agent_hud.changes import Changes
from agent_hud.models.board import Board
from agent_hud.server import build
from agent_hud.web import create_app
from tests.factories import as_json, put, remove


@pytest.fixture
def board() -> Board:
    return Board()


@pytest.fixture
def changes() -> Changes:
    return Changes()


@pytest.fixture
async def port(board: Board, changes: Changes, tmp_path: Path) -> AsyncIterator[int]:
    """The page server on a free port, in the test's event loop."""
    sock = socket.create_server(("127.0.0.1", 0))
    server = uvicorn.Server(uvicorn.Config(create_app(board, changes, tmp_path), log_config=None))
    task = asyncio.create_task(server.serve(sockets=[sock]))
    yield sock.getsockname()[1]
    server.should_exit = True
    await task


async def test_page_gets_the_board_on_connect_and_after_each_write(port: int, board: Board, changes: Changes) -> None:
    """Assemble: a page from the server's origin, connected to the websocket.
    Act: the agent writes, one op at a time.
    Assert: the page gets the board when it connects and after each write."""
    origin = f"http://127.0.0.1:{port}"
    async with (
        asyncio.timeout(5),
        Client(build(board, changes)) as agent,
        connect(f"ws://127.0.0.1:{port}/ws", origin=origin, proxy=None) as page,
    ):
        assert Board.model_validate_json(await page.recv()) == board
        for op in put("plan", "1. a"), put("risk", "locks"), remove("plan"):
            await agent.call_tool("write", {"ops": as_json(op)})
            assert Board.model_validate_json(await page.recv()) == board, f"page is not up to date after {op}"


@pytest.mark.parametrize(
    ("host", "origin"),
    [("127.0.0.1", "http://example.com"), ("example.com", "http://example.com:{port}")],
    ids=["other-site", "dns-rebinding"],
)
async def test_other_sites_cannot_connect(port: int, host: str, origin: str) -> None:
    """Assemble: the page server on 127.0.0.1.
    Act: open the websocket as a page from another site does.
    Assert: the handshake fails."""
    with pytest.raises(InvalidStatus):
        await connect(f"ws://{host}:{port}/ws", host="127.0.0.1", origin=origin.format(port=port), proxy=None)
