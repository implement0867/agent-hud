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
from websockets.asyncio.client import connect
from websockets.exceptions import InvalidStatus

from agent_hud.deps import get_store
from agent_hud.models.events import BoardEvent, EventKind, SendEvent
from agent_hud.models.ops import Op
from agent_hud.server import build
from agent_hud.settings import get_settings
from agent_hud.web import create_app
from tests.factories import as_json
from tests.strategies import card_ids, ops

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
    sock = socket.create_server(("127.0.0.1", 0))
    server = uvicorn.Server(uvicorn.Config(app, log_config=None))
    task = asyncio.create_task(server.serve(sockets=[sock]))
    yield sock.getsockname()
    server.should_exit = True
    await task


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


# Examples go over sockets, so their time varies more than the default deadline allows.
@given(writes())
@settings(deadline=None)
async def test_page_gets_the_board_on_connect_and_after_each_accepted_write(
    address: tuple[str, int], agent: Client[Any], writes: list[list[Op]]
) -> None:
    """Assemble: a new board, and a page from the app's origin.
    Act: the agent writes each batch of ops.
    Assert: the page gets the stored board on connect and after each accepted write."""
    get_store.cache_clear()
    host, port = address
    async with (
        asyncio.timeout(5),
        connect(f"ws://{host}:{port}/ws", origin=f"http://{host}:{port}", proxy=None) as page,
    ):
        assert BoardEvent.model_validate_json(await page.recv()).board == get_store().read()
        for batch in writes:
            result = await agent.call_tool("write", {"ops": as_json(*batch)}, raise_on_error=False)
            if not result.is_error:
                assert BoardEvent.model_validate_json(await page.recv()).board == get_store().read()


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


@given(st.lists(st.lists(st.text(), min_size=1)))
@settings(deadline=None)
async def test_agent_gets_each_sent_message_once_in_order(
    address: tuple[str, int], agent: Client[Any], batches: list[list[str]]
) -> None:
    """Assemble: a new store, and a page from the app's origin.
    Act: for each batch, the page sends its messages, then the agent waits until it has as many messages.
    Assert: each batch reaches the agent in the order sent, each message once."""
    get_store.cache_clear()
    host, port = address
    async with (
        asyncio.timeout(5),
        connect(f"ws://{host}:{port}/ws", origin=f"http://{host}:{port}", proxy=None) as page,
    ):
        for batch in batches:
            for message in batch:
                await page.send(SendEvent(kind=EventKind.send, message=message).model_dump_json())
            received: list[str] = []
            while len(received) < len(batch):
                received += (await agent.call_tool("wait", {})).data
            assert received == batch
