from collections.abc import AsyncIterator
from typing import Any

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from agent_hud.deps import get_store
from agent_hud.models.board import Board
from agent_hud.models.card import Reaction
from agent_hud.models.ops import TOp
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
    ops: list[TOp] = [put("plan", "1. a"), put("risk", "locks")]
    expected = Board()
    expected.apply(ops)
    await client.call_tool("write", {"ops": as_json(*ops)})
    assert await read_board(client) == expected


async def test_read_returns_the_feedback_on_list_items(client: Client[Any]) -> None:
    """Assemble: a card of a list with a reaction and a comment on its items.
    Act: read.
    Assert: read returns the stored board."""
    await client.call_tool("write", {"ops": as_json(put("plan", "1. a\n2. b"))})
    get_store().react_to_item("plan", 1, Reaction.approve)
    get_store().comment_on_item("plan", 2, "why b?")
    assert await read_board(client) == get_store().read()


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


async def test_read_and_listen_are_read_only(client: Client[Any]) -> None:
    """Assemble: a client connected to a new server.
    Act: list the tools.
    Assert: read and listen have the read-only hint, and write does not."""
    tools = await client.list_tools()
    hints = {tool.name: tool.annotations is not None and tool.annotations.read_only_hint for tool in tools}
    assert hints == {"write": False, "read": True, "listen": True}
