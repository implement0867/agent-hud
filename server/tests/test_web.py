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

from agent_hud.changes import Changes
from agent_hud.models.board import Board
from agent_hud.models.events import BoardEvent
from agent_hud.models.ops import Op
from agent_hud.server import build
from agent_hud.web import create_app
from tests.factories import as_json
from tests.strategies import boards, card_ids, ops

# One server for the module, because Hypothesis runs each test's examples on the same fixtures.
pytestmark = pytest.mark.asyncio(loop_scope="module")


@st.composite
def boards_and_writes(draw: st.DrawFn) -> tuple[Board, list[list[Op]]]:
    """A board and the ops of write calls on one pool of ids, so that removes hit cards that exist and cards that do not."""
    ids = st.sampled_from(draw(st.lists(card_ids(), min_size=1)))
    return draw(boards(ids)), draw(st.lists(st.lists(ops(ids), min_size=1)))


def host_names() -> st.SearchStrategy[str]:
    """Domain names in lowercase, as browsers send them in Host and Origin."""
    return domains().map(str.lower)


@pytest.fixture(scope="module")
def board() -> Board:
    return Board()


@pytest.fixture(scope="module")
def changes() -> Changes:
    return Changes()


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def address(
    board: Board, changes: Changes, tmp_path_factory: pytest.TempPathFactory
) -> AsyncIterator[tuple[str, int]]:
    """Host and port of the page server, in the module's event loop."""
    sock = socket.create_server(("127.0.0.1", 0))
    app = create_app(board, changes, tmp_path_factory.mktemp("static"))
    server = uvicorn.Server(uvicorn.Config(app, log_config=None))
    task = asyncio.create_task(server.serve(sockets=[sock]))
    yield sock.getsockname()
    server.should_exit = True
    await task


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def agent(board: Board, changes: Changes) -> AsyncIterator[Client[Any]]:
    async with Client(build(board, changes)) as client:
        yield client


# Examples go over sockets, so their time varies more than the default deadline allows.
@given(boards_and_writes())
@settings(deadline=None)
async def test_page_gets_the_board_on_connect_and_after_each_accepted_write(
    address: tuple[str, int], agent: Client[Any], board: Board, case: tuple[Board, list[list[Op]]]
) -> None:
    """Assemble: any cards on the server's board, and a page from the server's origin.
    Act: the agent writes each batch of ops.
    Assert: the page gets the board when it connects and after each write that the server accepts."""
    start, writes = case
    board.cards = start.cards
    host, port = address
    async with (
        asyncio.timeout(5),
        connect(f"ws://{host}:{port}/ws", origin=f"http://{host}:{port}", proxy=None) as page,
    ):
        assert BoardEvent.model_validate_json(await page.recv()).board == board
        for batch in writes:
            result = await agent.call_tool("write", {"ops": as_json(*batch)}, raise_on_error=False)
            if not result.is_error:
                assert BoardEvent.model_validate_json(await page.recv()).board == board


@given(host_names())
@settings(deadline=None)
async def test_pages_of_other_sites_cannot_connect(address: tuple[str, int], domain: str) -> None:
    """Assemble: the page server.
    Act: open the websocket with the Origin of another site.
    Assert: the handshake fails."""
    host, port = address
    with pytest.raises(InvalidStatus):
        await connect(f"ws://{host}:{port}/ws", origin=f"http://{domain}", proxy=None)


@given(host_names())
@settings(deadline=None)
async def test_other_host_names_cannot_connect(address: tuple[str, int], domain: str) -> None:
    """Assemble: the page server.
    Act: open the websocket by another host name with its own Origin, as a DNS rebinding page does.
    Assert: the handshake fails."""
    host, port = address
    with pytest.raises(InvalidStatus):
        await connect(f"ws://{domain}:{port}/ws", host=host, origin=f"http://{domain}:{port}", proxy=None)
