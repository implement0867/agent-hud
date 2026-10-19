from collections.abc import AsyncIterator
from typing import Any

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError
from mcp.types import TextContent

from agent_hud.server import build


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


@pytest.mark.parametrize(
    ("writes", "board"),
    [
        ([[{"op": "put", "id": "plan", "md": "1. a"}]], "plan:\n1. a"),
        ([[{"op": "put", "id": "plan", "md": "old"}], [{"op": "put", "id": "plan", "md": "new"}]], "plan:\nnew"),
        ([[{"op": "put", "id": "a", "md": "x"}, {"op": "put", "id": "b", "md": "y"}]], "a:\nx\n\nb:\ny"),
        ([[{"op": "put", "id": "a", "md": "x"}], [{"op": "remove", "id": "a"}]], "no cards"),
        ([], "no cards"),
    ],
    ids=["put", "replace", "two-cards", "remove", "empty"],
)
async def test_read_shows_the_cards_that_write_left(
    client: Client[Any], writes: list[list[dict[str, str]]], board: str
) -> None:
    for ops in writes:
        assert await call(client, "write", ops=ops) == "ok", f"write {ops} failed"
    assert await call(client, "read") == board


@pytest.mark.parametrize(
    ("ops", "error"),
    [
        (
            [{"op": "put", "id": "b", "md": "y"}, {"op": "remove", "id": "missing"}],
            "op 2 \\(remove\\): no card 'missing'",
        ),
        ([{"op": "move", "id": "a"}], "move"),
        ([{"op": "put", "id": "a", "md": ""}], "md"),
        ([{"op": "put", "id": "1a", "md": "x"}], "id"),
        ([], "ops"),
    ],
    ids=["missing-card", "unknown-op", "empty-md", "bad-id", "no-ops"],
)
async def test_rejected_write_changes_nothing(client: Client[Any], ops: list[dict[str, str]], error: str) -> None:
    await call(client, "write", ops=[{"op": "put", "id": "a", "md": "x"}])
    with pytest.raises(ToolError, match=error):
        await call(client, "write", ops=ops)
    assert await call(client, "read") == "a:\nx", "a rejected write must leave the board as it was"


async def test_only_read_is_read_only(client: Client[Any]) -> None:
    hints = {
        tool.name: tool.annotations is not None and tool.annotations.read_only_hint
        for tool in await client.list_tools()
    }
    assert hints == {"write": False, "read": True}
