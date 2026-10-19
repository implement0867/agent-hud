from collections.abc import AsyncIterator
from typing import Any

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError
from mcp.types import TextContent

from agent_hud.board import Board
from agent_hud.ops import Op
from agent_hud.server import build
from tests.factories import as_json, put, remove


@pytest.fixture
async def client() -> AsyncIterator[Client[Any]]:
    async with Client(build()) as client:
        yield client


async def call(client: Client[Any], tool: str, **args: object) -> str:
    match (await client.call_tool(tool, args)).content:
        case [TextContent(text=text)]:
            return text
        case other:
            raise AssertionError(f"{tool} returned {other}, not one text block")


async def test_read_returns_the_board_that_write_left(client: Client[Any]) -> None:
    """Assemble: a client connected to a new server.
    Act: write two cards, then read.
    Assert: read returns the rendered board with those cards."""
    ops: list[Op] = [put("plan", "1. a"), put("risk", "locks")]
    await call(client, "write", ops=as_json(*ops))
    assert await call(client, "read") == Board().apply(ops).render()


@pytest.mark.parametrize(
    "ops",
    [as_json(put("b", "y"), remove("missing")), []],
    ids=["missing-card", "no-ops"],
)
async def test_rejected_write_changes_nothing(client: Client[Any], ops: list[dict[str, Any]]) -> None:
    """Assemble: a server with card a.
    Act: send a write that the server rejects.
    Assert: ToolError, and read returns the same board as before."""
    await call(client, "write", ops=as_json(put("a", "x")))
    before = await call(client, "read")
    with pytest.raises(ToolError):
        await call(client, "write", ops=ops)
    assert await call(client, "read") == before, "a rejected write must leave the board as it was"


async def test_only_read_is_read_only(client: Client[Any]) -> None:
    """Assemble: a client connected to a new server.
    Act: list the tools.
    Assert: read has the read-only hint and write does not."""
    tools = await client.list_tools()
    hints = {tool.name: tool.annotations is not None and tool.annotations.read_only_hint for tool in tools}
    assert hints == {"write": False, "read": True}
