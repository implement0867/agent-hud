from collections.abc import AsyncIterator
from typing import Any

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from agent_hud.deps import get_hud
from agent_hud.models.actions import Action, Author, Reaction
from agent_hud.server import build
from tests.factories import as_json, comment, put, react, read_board, remove


@pytest.fixture
async def client() -> AsyncIterator[Client[Any]]:
    get_hud.cache_clear()
    async with Client(build()) as client:
        yield client


async def test_read_returns_the_board_with_its_threads(client: Client[Any]) -> None:
    """Assemble: a server where the agent put a card of a list and the user reacted and commented on its parts.
    Act: read.
    Assert: read returns the hud's board."""
    await client.call_tool("write", {"actions": as_json(put("plan", "1. a\n2. b"), put("risk", "locks"))})
    feedback = react("plan", Reaction.approve), comment("plan/2", "why b?")
    get_hud().act([Action(id=str(n), author=Author.user, body=body) for n, body in enumerate(feedback)])
    assert await read_board(client) == get_hud().board


@pytest.mark.parametrize(
    "actions",
    [as_json(put("b", "y"), remove("missing")), as_json(put("b", "y"), react("a/1", Reaction.reject)), []],
    ids=["missing-card", "missing-part", "no-actions"],
)
async def test_rejected_write_changes_nothing(client: Client[Any], actions: list[dict[str, Any]]) -> None:
    """Assemble: a server with card a.
    Act: send a write that the server rejects.
    Assert: ToolError, and read returns the same board as before."""
    await client.call_tool("write", {"actions": as_json(put("a", "x"))})
    before = await read_board(client)
    with pytest.raises(ToolError):
        await client.call_tool("write", {"actions": actions})
    assert await read_board(client) == before, "a rejected write must leave the board as it was"


async def test_read_and_listen_are_read_only(client: Client[Any]) -> None:
    """Assemble: a client connected to a new server.
    Act: list the tools.
    Assert: read and listen have the read-only hint, and write does not."""
    tools = await client.list_tools()
    hints = {tool.name: tool.annotations is not None and tool.annotations.read_only_hint for tool in tools}
    assert hints == {"write": False, "read": True, "listen": True}
