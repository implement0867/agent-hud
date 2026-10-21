import asyncio
import socket
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack
from typing import Any

import pytest
import pytest_asyncio
import uvicorn
from fastmcp import Client
from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.provisional import domains
from pydantic import ValidationError
from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import InvalidStatus

from agent_hud.deps import get_store
from agent_hud.models.board import Board
from agent_hud.models.card import Reaction
from agent_hud.models.events import (
    BoardChanged,
    CommentAdded,
    EventKind,
    ItemCommentAdded,
    ItemReactionSet,
    MessageReceived,
    MessageSent,
    ReactionSet,
)
from agent_hud.models.ops import TOp
from agent_hud.server import build
from agent_hud.settings import get_settings
from agent_hud.store import BoardStore
from agent_hud.web import create_app
from tests.factories import as_json, put
from tests.strategies import blanks, card_ids, item_texts, messages, numbered_list, ops, reactions

# One server for the module, because Hypothesis runs each test's examples on the same fixtures.
pytestmark = pytest.mark.asyncio(loop_scope="module")


@st.composite
def writes(draw: st.DrawFn) -> list[list[TOp]]:
    """The ops of write calls on one pool of ids, so that removes hit cards that exist and cards that do not."""
    ids = st.sampled_from(draw(st.lists(card_ids(), min_size=1)))
    return draw(st.lists(st.lists(ops(ids), min_size=1)))


def host_names() -> st.SearchStrategy[str]:
    """Domain names in lowercase, as browsers send them in Host and Origin."""
    return domains().map(str.lower)


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def address(tmp_path_factory: pytest.TempPathFactory) -> AsyncIterator[tuple[str, int]]:
    """Host and port of the app on a free port, in the module's event loop."""
    with pytest.MonkeyPatch.context() as env:
        env.setenv("AGENT_HUD_STATIC_DIR", str(tmp_path_factory.mktemp("static")))
        get_settings.cache_clear()
        app = create_app()
    get_settings.cache_clear()
    # With IPPROTO_TCP, asyncio turns off Nagle's algorithm on each connection, as for the socket uvicorn binds itself.
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
    sock.bind(("127.0.0.1", 0))
    sock.listen()
    server = uvicorn.Server(uvicorn.Config(app, log_config=None))
    task = asyncio.create_task(server.serve(sockets=[sock]))
    yield sock.getsockname()
    server.should_exit = True
    await task


@pytest.fixture(scope="module")
def store() -> BoardStore:
    """A new store for the module. The app and the agent get the same one from get_store."""
    get_store.cache_clear()
    return get_store()


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def page(address: tuple[str, int], store: BoardStore) -> AsyncIterator[ClientConnection]:
    """A page from the app's origin that has read the board it gets on connect."""
    host, port = address
    async with connect(f"ws://{host}:{port}/ws", origin=f"http://{host}:{port}", proxy=None) as page:
        await page.recv()
        yield page


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def listeners(address: tuple[str, int], store: BoardStore) -> AsyncIterator[list[ClientConnection]]:
    """Two agents' sockets for the user's messages, at the URL that the listen tool returns."""
    host, port = address
    async with Client(f"http://{host}:{port}/mcp/") as remote:
        url = (await remote.call_tool("listen", {})).data
    async with AsyncExitStack() as stack:
        yield [await stack.enter_async_context(connect(url, proxy=None)) for _ in range(2)]


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def agent() -> AsyncIterator[Client[Any]]:
    """The MCP tools in memory, on the same store as the app. MCP over HTTP is slower per call."""
    async with Client(build()) as client:
        yield client


async def test_app_serves_the_tools_over_http(address: tuple[str, int], agent: Client[Any]) -> None:
    """Assemble: the app, and the MCP tools in memory.
    Act: list the tools over HTTP at /mcp/.
    Assert: the same tools as in memory."""
    host, port = address
    async with Client(f"http://{host}:{port}/mcp/") as remote:
        assert await remote.list_tools() == await agent.list_tools()


async def test_page_gets_the_board_on_connect(address: tuple[str, int], store: BoardStore) -> None:
    """Assemble: the app.
    Act: open a page from the app's origin.
    Assert: the first event carries the stored board."""
    host, port = address
    async with connect(f"ws://{host}:{port}/ws", origin=f"http://{host}:{port}", proxy=None) as page:
        assert BoardChanged.model_validate_json(await page.recv()).board == store.read()


# Examples go over sockets, so their time varies more than the default deadline allows.
@given(writes())
@settings(deadline=None)
async def test_page_gets_the_board_after_each_accepted_write(
    page: ClientConnection, agent: Client[Any], store: BoardStore, writes: list[list[TOp]]
) -> None:
    """Assemble: a page on the app.
    Act: the agent writes each batch of ops.
    Assert: after each accepted write, the page gets the stored board."""
    async with asyncio.timeout(5):
        for batch in writes:
            result = await agent.call_tool("write", {"ops": as_json(*batch)}, raise_on_error=False)
            if not result.is_error:
                assert BoardChanged.model_validate_json(await page.recv()).board == store.read()


@given(card_ids(), st.text(min_size=1), reactions())
@settings(deadline=None)
async def test_page_and_agents_get_the_reaction_on_the_card(
    page: ClientConnection,
    listeners: list[ClientConnection],
    agent: Client[Any],
    card_id: str,
    md: str,
    reaction: Reaction | None,
) -> None:
    """Assemble: a card that the agent put, a page that got the board, and two agents' listeners.
    Act: the page sets a reaction on the card.
    Assert: the page gets the board with the reaction on the card, and each listener gets the reaction."""
    reaction_set = ReactionSet(kind=EventKind.reaction_set, id=card_id, reaction=reaction)
    async with asyncio.timeout(5):
        await agent.call_tool("write", {"ops": as_json(put(card_id, md))})
        await page.recv()
        await page.send(reaction_set.model_dump_json())
        assert BoardChanged.model_validate_json(await page.recv()).board.cards[card_id].reaction == reaction
        for listener in listeners:
            assert ReactionSet.model_validate_json(await listener.recv()) == reaction_set


@given(card_ids(), st.lists(item_texts(), min_size=1), reactions(), st.data())
@settings(deadline=None)
async def test_page_and_agents_get_the_reaction_on_the_item(
    page: ClientConnection,
    listeners: list[ClientConnection],
    agent: Client[Any],
    card_id: str,
    texts: list[str],
    reaction: Reaction | None,
    data: st.DataObject,
) -> None:
    """Assemble: a card of a numbered list that the agent put, a page that got the board, and two agents' listeners.
    Act: the page sets a reaction on one item.
    Assert: the page gets the board with the reaction on the item, and each listener gets the reaction."""
    number = data.draw(st.integers(1, len(texts)))
    item_reaction_set = ItemReactionSet(kind=EventKind.item_reaction_set, id=card_id, item=number, reaction=reaction)
    async with asyncio.timeout(5):
        await agent.call_tool("write", {"ops": as_json(put(card_id, numbered_list(texts)))})
        await page.recv()
        await page.send(item_reaction_set.model_dump_json())
        items = BoardChanged.model_validate_json(await page.recv()).board.cards[card_id].items
        assert items[number - 1].reaction == reaction
        for listener in listeners:
            assert ItemReactionSet.model_validate_json(await listener.recv()) == item_reaction_set


@given(card_ids(), st.text(min_size=1), messages())
@settings(deadline=None)
async def test_page_and_agents_get_the_comment_on_the_card(
    page: ClientConnection,
    listeners: list[ClientConnection],
    agent: Client[Any],
    card_id: str,
    md: str,
    text: str,
) -> None:
    """Assemble: a card that the agent put, a page that got the board, and two agents' listeners.
    Act: the page adds a comment to the card.
    Assert: the page gets the board with the comment on the card, and each listener gets the comment."""
    comment_added = CommentAdded(kind=EventKind.comment_added, id=card_id, text=text)
    async with asyncio.timeout(5):
        await agent.call_tool("write", {"ops": as_json(put(card_id, md))})
        await page.recv()
        await page.send(comment_added.model_dump_json())
        assert BoardChanged.model_validate_json(await page.recv()).board.cards[card_id].comments[0].text == text
        for listener in listeners:
            assert CommentAdded.model_validate_json(await listener.recv()) == comment_added


@given(card_ids(), st.lists(item_texts(), min_size=1), messages(), st.data())
@settings(deadline=None)
async def test_page_and_agents_get_the_comment_on_the_item(
    page: ClientConnection,
    listeners: list[ClientConnection],
    agent: Client[Any],
    card_id: str,
    texts: list[str],
    text: str,
    data: st.DataObject,
) -> None:
    """Assemble: a card of a numbered list that the agent put, a page that got the board, and two agents' listeners.
    Act: the page adds a comment to one item.
    Assert: the page gets the board with the comment on the item, and each listener gets the comment."""
    number = data.draw(st.integers(1, len(texts)))
    item_comment_added = ItemCommentAdded(kind=EventKind.item_comment_added, id=card_id, item=number, text=text)
    async with asyncio.timeout(5):
        await agent.call_tool("write", {"ops": as_json(put(card_id, numbered_list(texts)))})
        await page.recv()
        await page.send(item_comment_added.model_dump_json())
        items = BoardChanged.model_validate_json(await page.recv()).board.cards[card_id].items
        assert items[number - 1].comments[0].text == text
        for listener in listeners:
            assert ItemCommentAdded.model_validate_json(await listener.recv()) == item_comment_added


@pytest.mark.parametrize("path", ["/ws", "/agent"])
@given(host_names())
@settings(deadline=None)
async def test_pages_of_other_sites_cannot_connect(address: tuple[str, int], path: str, domain: str) -> None:
    """Assemble: the app.
    Act: open the websocket with the Origin of another site.
    Assert: the handshake fails."""
    host, port = address
    with pytest.raises(InvalidStatus):
        await connect(f"ws://{host}:{port}{path}", origin=f"http://{domain}", proxy=None)


@pytest.mark.parametrize("path", ["/ws", "/agent"])
@given(host_names())
@settings(deadline=None)
async def test_other_host_names_cannot_connect(address: tuple[str, int], path: str, domain: str) -> None:
    """Assemble: the app.
    Act: open the websocket by another host name with its own Origin, as a DNS rebinding page does.
    Assert: the handshake fails."""
    host, port = address
    with pytest.raises(InvalidStatus):
        await connect(f"ws://{domain}:{port}{path}", host=host, origin=f"http://{domain}:{port}", proxy=None)


@given(st.lists(st.lists(messages(), min_size=1)))
@settings(deadline=None)
async def test_agent_gets_each_sent_message_once_in_order(
    page: ClientConnection, listeners: list[ClientConnection], batches: list[list[str]]
) -> None:
    """Assemble: a page and two agents' listeners on the app.
    Act: for each batch, the page sends its messages.
    Assert: the page gets a receipt for each message, and each listener gets each message once, in the order sent."""
    async with asyncio.timeout(5):
        for batch in batches:
            for message in batch:
                await page.send(MessageSent(kind=EventKind.message_sent, message=message).model_dump_json())
            for _ in batch:
                MessageReceived.model_validate_json(await page.recv())
            for listener in listeners:
                assert [MessageSent.model_validate_json(await listener.recv()).message for _ in batch] == batch


@given(st.builds(BoardStore), messages(), st.lists(messages()))
async def test_a_listener_gets_the_messages_sent_after_the_last_listener_stopped(
    new_store: BoardStore, first: str, rest: list[str]
) -> None:
    """Assemble: a store whose only listener got one message and stopped.
    Act: add more messages, then listen again.
    Assert: the new listener has them in the order added."""
    with new_store.listen() as listener:
        new_store.add_message(first)
        assert listener.get_nowait() == MessageSent(kind=EventKind.message_sent, message=first)
    for message in rest:
        new_store.add_message(message)
    with new_store.listen() as listener:
        assert [listener.get_nowait() for _ in rest] == [
            MessageSent(kind=EventKind.message_sent, message=m) for m in rest
        ]


@given(st.builds(BoardStore), card_ids(), reactions())
async def test_a_reaction_to_a_missing_card_changes_nothing(
    new_store: BoardStore, card_id: str, reaction: Reaction | None
) -> None:
    """Assemble: an empty store, as after the agent removed the card the page showed.
    Act: react to the card.
    Assert: the board is still empty."""
    new_store.react(card_id, reaction)
    assert new_store.read() == Board()


@given(st.builds(BoardStore), card_ids(), st.lists(item_texts()), reactions(), st.integers(min_value=0))
async def test_a_reaction_to_a_missing_item_changes_nothing(
    new_store: BoardStore, card_id: str, texts: list[str], reaction: Reaction | None, extra: int
) -> None:
    """Assemble: a store with a card of a numbered list, or a missing card, as after the agent replaced or removed it.
    Act: react to an item after the last.
    Assert: the board is unchanged."""
    if texts:
        new_store.apply([put(card_id, numbered_list(texts))])
    before = new_store.read()
    new_store.react_to_item(card_id, len(texts) + 1 + extra, reaction)
    assert new_store.read() == before


@given(st.builds(BoardStore), card_ids(), messages())
async def test_a_comment_on_a_missing_card_changes_nothing(new_store: BoardStore, card_id: str, text: str) -> None:
    """Assemble: an empty store, as after the agent removed the card the page showed.
    Act: comment on the card.
    Assert: the board is still empty."""
    new_store.comment(card_id, text)
    assert new_store.read() == Board()


@given(st.builds(BoardStore), card_ids(), st.lists(item_texts()), messages(), st.integers(min_value=0))
async def test_a_comment_on_a_missing_item_changes_nothing(
    new_store: BoardStore, card_id: str, texts: list[str], text: str, extra: int
) -> None:
    """Assemble: a store with a card of a numbered list, or a missing card, as after the agent replaced or removed it.
    Act: comment on an item after the last.
    Assert: the board is unchanged."""
    if texts:
        new_store.apply([put(card_id, numbered_list(texts))])
    before = new_store.read()
    new_store.comment_on_item(card_id, len(texts) + 1 + extra, text)
    assert new_store.read() == before


@given(blanks())
async def test_a_sent_message_needs_a_character_that_is_not_white_space(blank: str) -> None:
    """Assemble: text of white space only, or no text.
    Act: make a MessageSent event of it.
    Assert: ValidationError."""
    with pytest.raises(ValidationError):
        MessageSent(kind=EventKind.message_sent, message=blank)
