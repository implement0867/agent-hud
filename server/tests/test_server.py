import re
from collections.abc import AsyncIterator
from typing import Any

import jsonschema
import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError
from hypothesis import given
from mcp.types import Tool

from agent_hud.boards import BoardRegistry
from agent_hud.hud import Hud
from agent_hud.models.actions import Action, ActionKind, Author, TAgentBody
from agent_hud.server import build_mcp_server
from tests.factories import as_json, comment, link, put, read_board, remove, resize, say, send, unlink
from tests.strategies import agent_bodies, card_ids


async def listed_write(client: Client[Any]) -> Tool:
    return next(tool for tool in await client.list_tools() if tool.name == "write")


@pytest.fixture
async def client(hud: Hud) -> AsyncIterator[Client[Any]]:
    """The MCP tools in memory, on the test's hud as the shared board."""
    async with Client(build_mcp_server(BoardRegistry(None, default_hud=hud))) as client:
        yield client


async def test_read_returns_the_board_with_its_threads(client: Client[Any], hud: Hud) -> None:
    """Assemble: a server where the agent put a card of a list and the user commented on the card and on its words.
    Act: read.
    Assert: read returns the hud's board."""
    await client.call_tool("write", {"actions": as_json(put("plan", "1. a\n2. b"), put("risk", "locks"))})
    feedback = comment("plan", "fine"), comment("plan", "why b?", "b")
    hud.act([Action(id=str(n), author=Author.user, body=body) for n, body in enumerate(feedback)])
    assert await read_board(client) == hud.board


async def test_read_of_cards_returns_what_is_on_them(client: Client[Any], hud: Hud) -> None:
    """Assemble: two cards with a thread, an arrow between them, a size and a version each, and a chat message.
    Act: read one card.
    Assert: that card with the thread, arrow, size and history on it, all the messages, and no more."""
    await client.call_tool("write", {"actions": as_json(put("plan", "1. a"), put("risk", "1. r"))})
    again = put("plan", "1. a\n2. b"), put("risk", "1. s")
    feedback = comment("plan", "ok", "a"), comment("risk", "no", "s"), link("why", "risk", "plan", quote="s")
    await client.call_tool("write", {"actions": as_json(*again, *feedback, say("hello"))})
    hud.act([Action(id="m", author=Author.user, body=resize("plan", 300, 200))])
    reading = await read_board(client, history=True, cards=["plan"])
    assert set(reading.cards) == {"plan"}
    assert [thread.card for thread in reading.threads.values()] == ["plan"]
    assert set(reading.sizes) == {"plan"}
    assert set(reading.arrows) == {"why"}
    assert set(reading.history) == {"plan"}
    assert [said.text for said in reading.messages] == ["ok", "no", "hello"]
    assert set(reading.positions) == set()
    assert set((await read_board(client, cards=["risk"])).arrows) == {"why"}


async def test_read_since_returns_the_messages_after_the_one_named(client: Client[Any]) -> None:
    """Assemble: three messages.
    Act: read since the second, and since an id that no message has.
    Assert: the third alone, then all three."""
    await client.call_tool("write", {"actions": as_json(say("one"), say("two"), say("three"))})
    [_, second, _] = (await read_board(client)).messages
    assert [said.text for said in (await read_board(client, since=second.id)).messages] == ["three"]
    assert [said.text for said in (await read_board(client, since="none")).messages] == ["one", "two", "three"]


async def test_read_since_a_turn_returns_the_cards_that_changed_after_it_and_the_messages(
    client: Client[Any], hud: Hud
) -> None:
    """Assemble: two cards and a message from the agent; the user comments on the first and sends; the agent puts a third card, comments on the second and says.
    Act: read since the send, with and without cards named; then since an id the log does not have.
    Assert: the cards the agent touched after the send, with the comment and the message after it; the first card alone when named with the third; and the whole board for the id the log does not have."""
    await client.call_tool("write", {"actions": as_json(put("a", "1. a"), put("b", "1. b"), say("review"))})
    hud.act([Action(id="r", author=Author.user, body=comment("a", "yes", "a"))])
    hud.act([Action(id="turn", author=Author.user, body=send())])
    await client.call_tool("write", {"actions": as_json(put("c", "1. c"), comment("b", "fine", "b"), say("done"))})
    board = await read_board(client, since="turn")
    assert (set(board.cards), [said.text for said in board.messages]) == ({"b", "c"}, ["fine", "done"])
    assert set((await read_board(client, since="turn", cards=["a", "c"])).cards) == {"c"}
    whole = await read_board(client, since="gone")
    assert (set(whole.cards), len(whole.messages)) == ({"a", "b", "c"}, 4)


async def test_read_leaves_out_the_history_unless_asked(client: Client[Any], hud: Hud) -> None:
    """Assemble: a server where the agent put a card, then put it again.
    Act: read, and read with the history.
    Assert: the first has no history, and the second has the hud's whole board."""
    await client.call_tool("write", {"actions": as_json(put("plan", "1. a"))})
    await client.call_tool("write", {"actions": as_json(put("plan", "1. b"))})
    assert (await read_board(client)).history == {}
    assert await read_board(client, history=True) == hud.board


@pytest.mark.parametrize(
    "actions",
    [as_json(put("b", "y"), remove("missing")), as_json(put("b", "y"), comment("a", "why?", "nope")), []],
    ids=["missing-card", "missing-words", "no-actions"],
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


async def test_write_returns_the_cards_it_put(client: Client[Any]) -> None:
    """Assemble: a client connected to a new server.
    Act: write a put of a card, a say, and a put of another card.
    Assert: the result names both cards as added, and no more."""
    result = await client.call_tool("write", {"actions": as_json(put("plan", "1. a"), say("hi"), put("risk", "locks"))})
    assert result.structured_content == {"added": ["plan", "risk"], "replaced": [], "retired": [], "dropped": []}


async def test_write_reports_the_threads_and_arrows_a_put_moves_aside(client: Client[Any], hud: Hud) -> None:
    """Assemble: a server with a plan of two items that the user commented on, with an arrow from each item to a note card and one from the note to the plan.
    Act: write a put of the plan with the second item changed, a put of a new card, an unlink of the arrow from the note, and a remove of the note.
    Assert: the result names the plan as replaced and the new card as added, the thread on the second item as gone to the history, and the arrow at it as dropped, not the one unlinked."""
    await client.call_tool("write", {"actions": as_json(put("plan", "1. a\n2. b"), put("note", "n"))})
    feedback = [comment("plan", "yes", "a"), comment("plan", "no", "b")]
    arrows = [
        link("one", "plan", "note", quote="a"),
        link("two", "plan", "note", quote="b"),
        link("back", "note", "plan"),
    ]
    hud.act([Action(id=str(n), author=Author.user, body=body) for n, body in enumerate([*feedback, *arrows])])
    actions = as_json(put("plan", "1. a\n2. c"), put("new", "x"), unlink("back"), remove("note"))
    result = await client.call_tool("write", {"actions": actions})
    assert result.structured_content == {
        "added": ["new"],
        "replaced": ["plan"],
        "retired": [{"card": "plan", "quote": "b"}],
        "dropped": ["one", "two"],
    }


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
    Assert: the actions of write are one object with a kind of each action kind but place and send, which are the page's, and the description gives the fields of each kind."""
    write = await listed_write(client)
    item = write.input_schema["properties"]["actions"]["items"]
    assert "oneOf" not in item, "a oneOf with an object for each kind costs the agent more tokens"
    pages = (ActionKind.place, ActionKind.send)
    assert item["properties"]["kind"]["enum"] == [kind for kind in ActionKind if kind not in pages]
    assert "put {id, md, version?}" in (write.description or "")
    assert "link {id, card, quote?, occurrence?, dst, text?}" in (write.description or "")
    assert "comment {card, quote?, occurrence?, text}" in (write.description or "")


@given(agent_bodies(card_ids()))
async def test_listed_write_schema_takes_each_action_that_write_takes(body: TAgentBody) -> None:
    """Assemble: a client connected to a new server.
    Act: check an action of each kind against the listed schema of write.
    Assert: the schema takes it, so that a client that checks the schema sends each action that the server takes."""
    async with Client(build_mcp_server(BoardRegistry(None, default_hud=Hud()))) as client:
        jsonschema.validate({"actions": as_json(body)}, (await listed_write(client)).input_schema)


@pytest.mark.parametrize(
    ("action", "reason"),
    [
        ({"kind": "put", "id": "a"}, "action 2 (put): md: Field required"),
        ({"kind": "remove", "id": "a", "md": "x"}, "action 2 (remove): md: not a field of remove"),
        ({"kind": "say", "text": " "}, "action 2 (say): text: String should match pattern '\\S'"),
        ({"kind": "comment", "card": "a", "quote": "x"}, "action 2 (comment): text: Field required"),
        ({"kind": "resize", "id": "a"}, "action 2 (resize): resize takes a width, a height or both"),
    ],
    ids=["missing-field", "field-of-another-kind", "blank-text", "missing-text", "resize-of-nothing"],
)
async def test_write_checks_each_action_against_its_kind(
    client: Client[Any], action: dict[str, Any], reason: str
) -> None:
    """Assemble: a server with card a.
    Act: write a say and an action that the listed schema takes and the model of its kind does not.
    Assert: ToolError that names the action, its kind and the field in one line, and read returns the same board as before."""
    await client.call_tool("write", {"actions": as_json(put("a", "1. x"))})
    before = await read_board(client)
    jsonschema.validate({"actions": [action]}, (await listed_write(client)).input_schema)
    with pytest.raises(ToolError, match=f"{re.escape(reason)}.*; no actions were applied$") as info:
        await client.call_tool("write", {"actions": [*as_json(say("hi")), action]})
    assert "\n" not in str(info.value), "the error must be one line"
    assert await read_board(client) == before, "the server must check each action against the model of its kind"


@pytest.mark.parametrize(
    ("action", "reason"),
    [
        ({"kind": "foo", "id": "a"}, "kind 'foo' is not one of"),
        ({"id": "a"}, "kind is missing: one of"),
        ({"kind": "send"}, "kind 'send' is not one of"),
    ],
    ids=["unknown-kind", "no-kind", "send"],
)
async def test_write_lists_the_kinds_for_an_action_of_no_kind(
    client: Client[Any], action: dict[str, Any], reason: str
) -> None:
    """Assemble: a client connected to a new server.
    Act: write an action whose kind is not one of the kinds, that has no kind, or whose kind is send, which is the page's.
    Assert: ToolError that names the action and lists the kinds of the agent in one line."""
    kinds = ", ".join(kind for kind in ActionKind if kind is not ActionKind.send)
    with pytest.raises(ToolError, match=f"action 1: {re.escape(reason)} {kinds}; no actions were applied$") as info:
        await client.call_tool("write", {"actions": [action]})
    assert "\n" not in str(info.value), "the error must be one line"


async def test_write_names_the_action_that_does_not_fit_the_board(client: Client[Any]) -> None:
    """Assemble: a server with card a of one list item.
    Act: write a say, a comment on words that card a does not show, and a say.
    Assert: ToolError names the second action and its kind, says what to quote, and says that no action was applied."""
    await client.call_tool("write", {"actions": as_json(put("a", "1. x"))})
    reason = (
        "action 2 (comment): card 'a' does not show the words 'y': quote its text without markdown; "
        "no actions were applied"
    )
    with pytest.raises(ToolError, match=f"{re.escape(reason)}$"):
        actions = as_json(say("hi"), comment("a", "why?", "y"), say("there"))
        await client.call_tool("write", {"actions": actions})


async def test_write_rejects_a_second_put_of_a_card_in_one_batch(client: Client[Any]) -> None:
    """Assemble: a client connected to a new server.
    Act: write two puts of the same card.
    Assert: ToolError names the second put and the action that already puts the card, and the board has no card."""
    reason = "action 2 (put): card 'a' is already put by action 1; no actions were applied"
    with pytest.raises(ToolError, match=f"{re.escape(reason)}$"):
        await client.call_tool("write", {"actions": as_json(put("a", "x"), put("a", "y"))})
    assert (await read_board(client)).cards == {}


async def test_write_rejects_a_number_given_as_text(client: Client[Any]) -> None:
    """Assemble: a server with card a.
    Act: write a move whose x is the text of a number.
    Assert: ToolError names the field, and the card has no position."""
    await client.call_tool("write", {"actions": as_json(put("a", "x"))})
    with pytest.raises(ToolError, match=r"action 1 \(move\): x: Input should be a valid number"):
        await client.call_tool("write", {"actions": [{"kind": "move", "id": "a", "x": "10", "y": 0}]})
    assert (await read_board(client)).positions == {}


async def test_write_stamps_the_time_on_what_is_said(client: Client[Any]) -> None:
    """Act: the agent says a message.
    Assert: the message in the board has the time, with a time zone."""
    await client.call_tool("write", {"actions": as_json(say("now"))})
    [said] = (await read_board(client)).messages
    assert said.at is not None and said.at.tzinfo is not None
