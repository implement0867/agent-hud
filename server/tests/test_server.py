from collections.abc import AsyncIterator
from typing import Any

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from agent_hud.deps import get_store
from agent_hud.models.board import Board
from agent_hud.models.ops import Op
from agent_hud.server import build
from tests.factories import as_json, put, read_board, remove


@pytest.fixture
async def client() -> AsyncIterator[Client[Any]]:
    get_store.cache_clear()
    async with Client(build()) as client:
        yield client


async def test_read_returns_the_board_that_write_left(client: Client[Any]) -> None:
    """Assemble: a client connected to a server with an empty board.
    Act: write two cards, then read.
    Assert: read returns the board that the same ops give locally."""
    ops: list[Op] = [put("plan", "1. a"), put("risk", "locks")]
    expected = Board()
    expected.apply(ops)
    await client.call_tool("write", {"ops": as_json(*ops)})
    assert await read_board(client) == expected


@pytest.mark.parametrize(
    "ops",
    [as_json(put("b", "y"), remove("missing")), []],
    ids=["missing-card", "no-ops"],
)
async def test_rejected_write_changes_nothing(client: Client[Any], ops: list[dict[str, Any]]) -> None:
    """Assemble: a server with card a.
    Act: send a write that the server rejects.
    Assert: ToolError, and read returns the same board as before."""
    await client.call_tool("write", {"ops": as_json(put("a", "x"))})
    before = await read_board(client)
    with pytest.raises(ToolError):
        await client.call_tool("write", {"ops": ops})
    assert await read_board(client) == before, "a rejected write must leave the board as it was"


async def test_only_read_is_read_only(client: Client[Any]) -> None:
    """Assemble: a client connected to a new server.
    Act: list the tools.
    Assert: read has the read-only hint, and write and wait do not."""
    tools = await client.list_tools()
    hints = {tool.name: tool.annotations is not None and tool.annotations.read_only_hint for tool in tools}
    assert hints == {"write": False, "read": True, "wait": False}
