import asyncio
import socket
from collections.abc import AsyncIterator
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
from agent_hud.models.events import EventKind, MessageReceived, MessageSent, Turn, ViewChanged
from agent_hud.models.ops import Op
from agent_hud.server import build
from agent_hud.settings import get_settings
from agent_hud.store import BoardStore
from agent_hud.web import create_app
from tests.factories import as_json, page_event, sent
from tests.strategies import blanks, card_ids, messages, ops

# One server for the module, because Hypothesis runs each test's examples on the same fixtures.
pytestmark = pytest.mark.asyncio(loop_scope="module")


@st.composite
def writes(draw: st.DrawFn) -> list[list[Op]]:
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
        assert ViewChanged.model_validate_json(await page.recv()).view == store.view()


# Examples go over sockets, so their time varies more than the default deadline allows.
@given(writes())
@settings(deadline=None)
async def test_page_gets_the_board_after_each_accepted_write(
    page: ClientConnection, agent: Client[Any], store: BoardStore, writes: list[list[Op]]
) -> None:
    """Assemble: a page on the app.
    Act: the agent writes each batch of ops.
    Assert: after each accepted write, the page gets the stored board."""
    async with asyncio.timeout(5):
        for batch in writes:
            result = await agent.call_tool("write", {"ops": as_json(*batch)}, raise_on_error=False)
            if not result.is_error:
                assert ViewChanged.model_validate_json(await page.recv()).view == store.view()


@given(host_names())
@settings(deadline=None)
async def test_pages_of_other_sites_cannot_connect(address: tuple[str, int], domain: str) -> None:
    """Assemble: the app.
    Act: open the websocket with the Origin of another site.
    Assert: the handshake fails."""
    host, port = address
    with pytest.raises(InvalidStatus):
        await connect(f"ws://{host}:{port}/ws", origin=f"http://{domain}", proxy=None)


@given(host_names())
@settings(deadline=None)
async def test_other_host_names_cannot_connect(address: tuple[str, int], domain: str) -> None:
    """Assemble: the app.
    Act: open the websocket by another host name with its own Origin, as a DNS rebinding page does.
    Assert: the handshake fails."""
    host, port = address
    with pytest.raises(InvalidStatus):
        await connect(f"ws://{domain}:{port}/ws", host=host, origin=f"http://{domain}:{port}", proxy=None)


@given(st.lists(st.lists(messages(), min_size=1)))
@settings(deadline=None)
async def test_agent_gets_each_sent_message_once_in_order(
    page: ClientConnection, agent: Client[Any], store: BoardStore, batches: list[list[str]]
) -> None:
    """Assemble: a page on the app.
    Act: for each batch, the page sends its messages, and when the server has confirmed them, the agent waits.
    Assert: each wait returns its batch in the order sent, each message once, and the page gets the view after it."""
    async with asyncio.timeout(5):
        for batch in batches:
            for message in batch:
                await page.send(sent(message))
            for _ in batch:
                MessageReceived.model_validate_json(await page.recv())
            assert (await agent.call_tool("wait", {})).data == batch
            assert ViewChanged.model_validate_json(await page.recv()).view == store.view()


@given(messages())
@settings(deadline=None)
async def test_page_has_the_turn_while_the_agent_waits(
    page: ClientConnection, agent: Client[Any], store: BoardStore, message: str
) -> None:
    """Assemble: a page on the app.
    Act: the agent waits, and the page sends a message when it gets the user's turn.
    Assert: the wait returns the message, and the page gets the receipt and the agent's turn, in either order."""
    async with asyncio.timeout(5), asyncio.TaskGroup() as tg:
        waiting = tg.create_task(agent.call_tool("wait", {}))
        assert ViewChanged.model_validate_json(await page.recv()).view.turn == Turn.user
        await page.send(sent(message))
        assert (await waiting).data == [message]
        events = [page_event(await page.recv()) for _ in range(2)]
        assert MessageReceived(kind=EventKind.message_received) in events
        assert ViewChanged(kind=EventKind.view_changed, view=store.view()) in events


@given(blanks())
async def test_a_sent_message_needs_a_character_that_is_not_white_space(blank: str) -> None:
    """Assemble: text of white space only, or no text.
    Act: make a MessageSent event of it.
    Assert: ValidationError."""
    with pytest.raises(ValidationError):
        MessageSent(kind=EventKind.message_sent, message=blank)
