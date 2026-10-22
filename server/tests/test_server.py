from collections.abc import AsyncIterator
from typing import Any

import jsonschema
import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError
from hypothesis import given
from mcp.types import Tool

from agent_hud.deps import get_hud
from agent_hud.models.actions import Action, ActionKind, Author, Reaction, TBody
from agent_hud.server import build
from tests.factories import as_json, comment, put, react, read_board, remove
from tests.strategies import bodies, card_ids


async def listed_write(client: Client[Any]) -> Tool:
    return next(tool for tool in await client.list_tools() if tool.name == "write")


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


async def test_read_leaves_out_the_history_unless_asked(client: Client[Any]) -> None:
    """Assemble: a server where the agent put a card, then put it again.
    Act: read, and read with the history.
    Assert: the first has no history, and the second has the hud's whole board."""
    await client.call_tool("write", {"actions": as_json(put("plan", "1. a"), put("plan", "1. b"))})
    assert (await read_board(client)).history == {}
    assert await read_board(client, history=True) == get_hud().board


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


async def test_write_lists_one_object_for_all_kinds_of_action(client: Client[Any]) -> None:
    """Assemble: a client connected to a new server.
    Act: list the tools.
    Assert: the actions of write are one object with a kind of each action kind, and the description gives the fields of each kind."""
    write = await listed_write(client)
    item = write.input_schema["properties"]["actions"]["items"]
    assert "oneOf" not in item, "a oneOf with an object for each kind costs the agent more tokens"
    assert item["properties"]["kind"]["enum"] == list(ActionKind)
    assert "put {id, md}" in (write.description or "")
    assert "link {id, src, dst, text?}" in (write.description or "")


@given(bodies(card_ids()))
async def test_listed_write_schema_takes_each_action_that_write_takes(body: TBody) -> None:
    """Assemble: a client connected to a new server.
    Act: check an action of each kind against the listed schema of write.
    Assert: the schema takes it, so that a client that checks the schema sends each action that the server takes."""
    async with Client(build()) as client:
        jsonschema.validate({"actions": as_json(body)}, (await listed_write(client)).input_schema)


@pytest.mark.parametrize(
    "action",
    [
        {"kind": "put", "id": "a"},
        {"kind": "remove", "id": "a", "md": "x"},
        {"kind": "say", "text": " "},
        {"kind": "react", "ref": "a/1"},
    ],
    ids=["missing-field", "field-of-another-kind", "blank-text", "missing-reaction"],
)
async def test_write_checks_each_action_against_its_kind(client: Client[Any], action: dict[str, Any]) -> None:
    """Assemble: a server with card a.
    Act: write an action that the listed schema takes and the model of its kind does not.
    Assert: ToolError, and read returns the same board as before."""
    await client.call_tool("write", {"actions": as_json(put("a", "1. x"))})
    before = await read_board(client)
    jsonschema.validate({"actions": [action]}, (await listed_write(client)).input_schema)
    with pytest.raises(ToolError):
        await client.call_tool("write", {"actions": [action]})
    assert await read_board(client) == before, "the server must check each action against the model of its kind"
