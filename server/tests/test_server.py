import asyncio
import re
from collections import defaultdict
from collections.abc import AsyncIterator
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import jsonschema
import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError
from hypothesis import given
from mcp.client.subscriptions import ServerEvent, Subscription, listen
from mcp.server.subscriptions import InMemorySubscriptionBus
from mcp.shared.subscriptions import ResourcesListChanged, ResourceUpdated
from mcp.types import TextResourceContents, Tool
from sqlalchemy import Engine

from agent_hud.boards import TBoardName
from agent_hud.database import open_database
from agent_hud.models.actions import Action, ActionKind, Author, TAgentBody
from agent_hud.models.board import Board
from agent_hud.presence import Presence
from agent_hud.server import build_mcp_server
from agent_hud.settings import Settings
from tests.factories import (
    BOARD,
    StoredBoard,
    as_json,
    comment,
    link,
    move,
    put,
    read_board,
    read_changes,
    remove,
    resize,
    say,
    unlink,
)
from tests.strategies import agent_bodies, card_ids


async def listed_write(client: Client[Any]) -> Tool:
    return next(tool for tool in await client.list_tools() if tool.name == "write")


@pytest.fixture
async def client(
    engine: Engine, presences: defaultdict[TBoardName, Presence], board: StoredBoard, tmp_path: Path
) -> AsyncIterator[Client[Any]]:
    """The MCP tools in memory, on the test's database, whose one board is BOARD."""
    settings = Settings(state_dir=tmp_path, static_dir=tmp_path, data_dir=tmp_path)
    async with Client(build_mcp_server(settings, engine, presences, InMemorySubscriptionBus())) as client:
        yield client


async def test_read_returns_the_board_with_its_threads(client: Client[Any], board: StoredBoard) -> None:
    """Assemble: a server where the agent put a card of a list and the user commented on the card and on its words.
    Act: read.
    Assert: read returns the board."""
    await client.call_tool(
        "write", {"name": BOARD, "actions": as_json(put("plan", "1. a\n2. b"), put("risk", "locks"))}
    )
    feedback = comment("plan", "fine"), comment("plan", "why b?", "b")
    board.act([Action(id=str(n), author=Author.user, body=body) for n, body in enumerate(feedback)])
    assert await read_board(client) == board.board


async def test_read_of_cards_returns_what_is_on_them(client: Client[Any], board: StoredBoard) -> None:
    """Assemble: two cards with a thread, an arrow between them, a size and a version each, and a chat message.
    Act: read one card.
    Assert: that card with the thread, arrow, size and history on it, all the messages, and no more."""
    await client.call_tool("write", {"name": BOARD, "actions": as_json(put("plan", "1. a"), put("risk", "1. r"))})
    again = put("plan", "1. a\n2. b"), put("risk", "1. s")
    feedback = comment("plan", "ok", "a"), comment("risk", "no", "s"), link("why", "risk", "plan", quote="s")
    await client.call_tool("write", {"name": BOARD, "actions": as_json(*again, *feedback, say("hello"))})
    board.act([Action(id="m", author=Author.user, body=resize("plan", 300, 200))])
    reading = await read_board(client, history=True, cards=["plan"])
    assert set(reading.cards) == {"plan"}
    assert [thread.card for thread in reading.threads.values()] == ["plan"]
    assert set(reading.sizes) == {"plan"}
    assert set(reading.arrows) == {"why"}
    assert set(reading.history) == {"plan"}
    assert [said.text for said in reading.messages] == ["ok", "no", "hello"]
    assert set(reading.positions) == set()
    assert set((await read_board(client, cards=["risk"])).arrows) == {"why"}


async def test_read_changes_returns_what_changed_since_the_last_read(client: Client[Any], board: StoredBoard) -> None:
    """Assemble: two cards from the agent, which then reads the board; the user comments on the first; the agent puts a third card and says.
    Act: read the changes twice; then the user moves the second card, and read the changes again.
    Assert: the first read has the first and third cards, the comment and the message; the second read has nothing; the last has the second card alone."""
    await client.call_tool("write", {"name": BOARD, "actions": as_json(put("a", "1. a"), put("b", "1. b"))})
    await read_board(client)
    board.act([Action(id="r", author=Author.user, body=comment("a", "yes", "a"))])
    await client.call_tool("write", {"name": BOARD, "actions": as_json(put("c", "1. c"), say("done"))})
    first = await read_changes(client)
    assert (set(first.cards), [said.text for said in first.messages]) == ({"a", "c"}, ["yes", "done"])
    second = await read_changes(client)
    assert (set(second.cards), second.messages) == (set(), ())
    board.act([Action(id="m", author=Author.user, body=move("b", 1, 1))])
    assert set((await read_changes(client)).cards) == {"b"}


async def test_read_leaves_out_the_history_unless_asked(client: Client[Any], board: StoredBoard) -> None:
    """Assemble: a server where the agent put a card, then put it again.
    Act: read, and read with the history.
    Assert: the first has no history, and the second has the whole board."""
    await client.call_tool("write", {"name": BOARD, "actions": as_json(put("plan", "1. a"))})
    await client.call_tool("write", {"name": BOARD, "actions": as_json(put("plan", "1. b"))})
    assert (await read_board(client)).history == {}
    assert await read_board(client, history=True) == board.board


@pytest.mark.parametrize(
    "actions",
    [as_json(put("b", "y"), remove("missing")), as_json(put("b", "y"), comment("a", "why?", "nope")), []],
    ids=["missing-card", "missing-words", "no-actions"],
)
async def test_rejected_write_changes_nothing(client: Client[Any], actions: list[dict[str, Any]]) -> None:
    """Assemble: a server with card a.
    Act: send a write that the server rejects.
    Assert: ToolError, and read returns the same board as before."""
    await client.call_tool("write", {"name": BOARD, "actions": as_json(put("a", "x"))})
    before = await read_board(client)
    with pytest.raises(ToolError):
        await client.call_tool("write", {"name": BOARD, "actions": actions})
    assert await read_board(client) == before, "a rejected write must leave the board as it was"


async def test_write_returns_the_cards_it_put(client: Client[Any]) -> None:
    """Assemble: a client connected to a new server.
    Act: write a put of a card, a say, and a put of another card.
    Assert: the result names both cards as added, and no more."""
    result = await client.call_tool(
        "write", {"name": BOARD, "actions": as_json(put("plan", "1. a"), say("hi"), put("risk", "locks"))}
    )
    assert result.structured_content == {"added": ["plan", "risk"], "replaced": [], "retired": [], "dropped": []}


async def test_write_reports_the_threads_and_arrows_a_put_moves_aside(client: Client[Any], board: StoredBoard) -> None:
    """Assemble: a server with a plan of two items that the user commented on, with an arrow from each item to a note card and one from the note to the plan.
    Act: write a put of the plan with the second item changed, a put of a new card, an unlink of the arrow from the note, and a remove of the note.
    Assert: the result names the plan as replaced and the new card as added, the thread on the second item as gone to the history, and the arrow at it as dropped, not the one unlinked."""
    await client.call_tool("write", {"name": BOARD, "actions": as_json(put("plan", "1. a\n2. b"), put("note", "n"))})
    feedback = [comment("plan", "yes", "a"), comment("plan", "no", "b")]
    arrows = [
        link("one", "plan", "note", quote="a"),
        link("two", "plan", "note", quote="b"),
        link("back", "note", "plan"),
    ]
    board.act([Action(id=str(n), author=Author.user, body=body) for n, body in enumerate([*feedback, *arrows])])
    actions = as_json(put("plan", "1. a\n2. c"), put("new", "x"), unlink("back"), remove("note"))
    result = await client.call_tool("write", {"name": BOARD, "actions": actions})
    assert result.structured_content == {
        "added": ["new"],
        "replaced": ["plan"],
        "retired": [{"card": "plan", "quote": "b"}],
        "dropped": ["one", "two"],
    }


async def test_the_reads_listen_and_list_boards_are_read_only(client: Client[Any]) -> None:
    """Assemble: a client connected to a new server.
    Act: list the tools.
    Assert: read, read_changes, listen and list_boards have the read-only hint, and the tools that change a board do not."""
    tools = await client.list_tools()
    hints = {tool.name: tool.annotations is not None and tool.annotations.read_only_hint is True for tool in tools}
    assert hints == {
        "write": False,
        "read": True,
        "read_changes": True,
        "listen": True,
        "create_board": False,
        "list_boards": True,
        "delete_board": False,
    }


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
    unused = Settings(state_dir=Path("unused"), data_dir=Path("unused"))
    with TemporaryDirectory() as directory:
        engine = open_database(Path(directory) / "agent-hud.db")
        async with Client(build_mcp_server(unused, engine, defaultdict(Presence), InMemorySubscriptionBus())) as client:
            jsonschema.validate({"name": BOARD, "actions": as_json(body)}, (await listed_write(client)).input_schema)
        engine.dispose()


@pytest.mark.parametrize(
    ("action", "reason"),
    [
        ({"kind": "put", "id": "a"}, "actions.1.put.md\n  Field required"),
        ({"kind": "remove", "id": "a", "md": "x"}, "actions.1.remove.md\n  Extra inputs are not permitted"),
        ({"kind": "say", "text": " "}, "actions.1.say.text\n  String should match pattern '\\S'"),
        ({"kind": "comment", "card": "a", "quote": "x"}, "actions.1.comment.text\n  Field required"),
        ({"kind": "resize", "id": "a"}, "actions.1.resize\n  Value error, resize takes a width, a height or both"),
        ({"kind": "move", "id": "a", "x": "10", "y": 0}, "actions.1.move.x\n  Input should be a valid number"),
        ({"kind": "foo", "id": "a"}, "actions.1\n  Input tag 'foo' found using 'kind' does not match"),
        ({"id": "a"}, "actions.1\n  Unable to extract tag using discriminator 'kind'"),
        ({"kind": "send"}, "actions.1\n  Input tag 'send' found using 'kind' does not match"),
    ],
    ids=[
        "missing-field",
        "field-of-another-kind",
        "blank-text",
        "missing-text",
        "resize-of-nothing",
        "number-as-text",
        "unknown-kind",
        "no-kind",
        "send",
    ],
)
async def test_write_checks_each_action_against_its_kind_before_it_runs(
    client: Client[Any], action: dict[str, Any], reason: str
) -> None:
    """Assemble: a server with card a.
    Act: write a say and an action that the model of its kind, or the union of the agent's kinds, does not take.
    Assert: ToolError with Pydantic's error at the action and its field, and read returns the same board as before."""
    await client.call_tool("write", {"name": BOARD, "actions": as_json(put("a", "1. x"))})
    before = await read_board(client)
    with pytest.raises(ToolError, match=re.escape(reason)):
        await client.call_tool("write", {"name": BOARD, "actions": [*as_json(say("hi")), action]})
    assert await read_board(client) == before, "the server must check each action against the model of its kind"


async def test_the_listed_schema_takes_an_action_that_its_kind_does_not(client: Client[Any]) -> None:
    """Act: check a put without its md against the listed schema of write.
    Assert: the schema takes it, since it is one object for all kinds; the tool checks the action against its kind."""
    jsonschema.validate(
        {"name": BOARD, "actions": [{"kind": "put", "id": "a"}]}, (await listed_write(client)).input_schema
    )


async def test_write_names_the_action_that_does_not_fit_the_board(client: Client[Any]) -> None:
    """Assemble: a server with card a of one list item.
    Act: write a say, a comment on words that card a does not show, and a say.
    Assert: ToolError names the second action and its kind, says what to quote, and says that no action was applied."""
    await client.call_tool("write", {"name": BOARD, "actions": as_json(put("a", "1. x"))})
    reason = (
        "action 2 (comment): card 'a' does not show the words 'y': quote its text without markdown; "
        "no actions were applied"
    )
    with pytest.raises(ToolError, match=f"{re.escape(reason)}$"):
        actions = as_json(say("hi"), comment("a", "why?", "y"), say("there"))
        await client.call_tool("write", {"name": BOARD, "actions": actions})


async def test_write_rejects_a_second_put_of_a_card_in_one_batch(client: Client[Any]) -> None:
    """Assemble: a client connected to a new server.
    Act: write two puts of the same card.
    Assert: ToolError names the second put and the action that already puts the card, and the board has no card."""
    reason = "action 2 (put): card 'a' is already put by action 1"
    with pytest.raises(ToolError, match=re.escape(reason)):
        await client.call_tool("write", {"name": BOARD, "actions": as_json(put("a", "x"), put("a", "y"))})
    assert (await read_board(client)).cards == {}


async def test_write_stamps_the_time_on_what_is_said(client: Client[Any]) -> None:
    """Act: the agent says a message.
    Assert: the message in the board has the time, with a time zone."""
    await client.call_tool("write", {"name": BOARD, "actions": as_json(say("now"))})
    [said] = (await read_board(client)).messages
    assert said.at is not None and said.at.tzinfo is not None


async def next_event(events: Subscription, wanted: ServerEvent) -> None:
    """Take events until the wanted one. TimeoutError when it does not come in five seconds."""
    async with asyncio.timeout(5):
        async for event in events:
            if event == wanted:
                return


async def test_each_board_is_a_resource_that_tells_its_subscribers_of_each_change(client: Client[Any]) -> None:
    """Assemble: a client that listens to the board's resource and to the list of resources.
    Act: write a card on the board, then create a board and delete it.
    Assert: an update of the board's resource comes after the write, and the resource is the board as JSON with the
    card; a change of the list comes after the create and after the delete, which add and remove the board's resource."""
    uri = f"board://{BOARD}"
    async with listen(client.session, resource_subscriptions=[uri], resources_list_changed=True) as events:
        await client.call_tool("write", {"name": BOARD, "actions": as_json(put("plan", "1. a"))})
        await next_event(events, ResourceUpdated(uri=uri))
        [content] = await client.read_resource(uri)
        assert isinstance(content, TextResourceContents)
        assert list(Board.model_validate_json(content.text).cards) == ["plan"]
        await client.call_tool("create_board", {"name": "other"})
        await next_event(events, ResourcesListChanged())
        assert {str(resource.uri) for resource in await client.list_resources()} == {uri, "board://other"}
        await client.call_tool("delete_board", {"name": "other"})
        await next_event(events, ResourcesListChanged())
        assert {str(resource.uri) for resource in await client.list_resources()} == {uri}


async def test_a_tool_on_a_board_that_is_not_there_fails(client: Client[Any]) -> None:
    """Act: read, write, listen to and delete a board that no one created.
    Assert: ToolError each time, which names the board and says how to make one."""
    for tool, arguments in [
        ("read", {}),
        ("write", {"actions": as_json(say("hi"))}),
        ("listen", {}),
        ("delete_board", {}),
    ]:
        with pytest.raises(ToolError, match=r"no board 'nowhere'.*create_board makes one"):
            await client.call_tool(tool, {"name": "nowhere", **arguments})
