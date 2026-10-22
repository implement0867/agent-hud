import asyncio
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack
from typing import Any

import pytest
import pytest_asyncio
from fastmcp import Client
from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.provisional import domains
from pydantic import ValidationError
from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import InvalidStatus

from agent_hud.deps import get_hud
from agent_hud.hud import Hud
from agent_hud.models.actions import Action, Author, TBody
from agent_hud.models.events import Accepted, PageEventAdapter, Rejected, Request, Snapshot
from agent_hud.server import build
from tests.factories import as_json, put, say
from tests.strategies import action_ids, blanks, bodies, card_ids, mds, messages

# One server for the module, because Hypothesis runs each test's examples on the same fixtures.
pytestmark = pytest.mark.asyncio(loop_scope="module")


@st.composite
def writes(draw: st.DrawFn) -> list[list[TBody]]:
    """The actions of write calls on one pool of ids, so that some fit the board and some do not."""
    ids = st.sampled_from(draw(st.lists(card_ids(), min_size=1)))
    return draw(st.lists(st.lists(bodies(ids), min_size=1)))


def host_names() -> st.SearchStrategy[str]:
    """Domain names in lowercase, as browsers send them in Host and Origin."""
    return domains().map(str.lower)


async def reply(page: ClientConnection) -> tuple[Accepted | Rejected, list[Snapshot]]:
    """The reply to the page's request, and the boards the page got before it."""
    snapshots: list[Snapshot] = []
    while True:
        match PageEventAdapter.validate_json(await page.recv()):
            case Snapshot() as snapshot:
                snapshots.append(snapshot)
            case Accepted() | Rejected() as answer:
                return answer, snapshots


@pytest.fixture(scope="module")
def hud() -> Hud:
    """A new hud for the module. The app and the agent get the same one from get_hud."""
    get_hud.cache_clear()
    return get_hud()


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def page(address: tuple[str, int], hud: Hud) -> AsyncIterator[ClientConnection]:
    """A page from the app's origin that has read the board it gets on connect."""
    host, port = address
    async with connect(f"ws://{host}:{port}/ws", origin=f"http://{host}:{port}", proxy=None) as page:
        await page.recv()
        yield page


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def listeners(address: tuple[str, int], hud: Hud) -> AsyncIterator[list[ClientConnection]]:
    """Two agents' sockets for the user's actions, at the URL that the listen tool returns."""
    host, port = address
    async with Client(f"http://{host}:{port}/mcp/") as remote:
        url = (await remote.call_tool("listen", {})).data
    async with AsyncExitStack() as stack:
        yield [await stack.enter_async_context(connect(url, proxy=None)) for _ in range(2)]


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def agent() -> AsyncIterator[Client[Any]]:
    """The MCP tools in memory, on the same hud as the app. MCP over HTTP is slower per call."""
    async with Client(build()) as client:
        yield client


async def test_app_serves_the_tools_over_http(address: tuple[str, int], agent: Client[Any]) -> None:
    """Assemble: the app, and the MCP tools in memory.
    Act: list the tools over HTTP at /mcp/.
    Assert: the same tools as in memory."""
    host, port = address
    async with Client(f"http://{host}:{port}/mcp/") as remote:
        assert await remote.list_tools() == await agent.list_tools()


async def test_page_gets_the_board_on_connect(address: tuple[str, int], hud: Hud) -> None:
    """Assemble: the app.
    Act: open a page from the app's origin.
    Assert: the first event carries the board."""
    host, port = address
    async with connect(f"ws://{host}:{port}/ws", origin=f"http://{host}:{port}", proxy=None) as page:
        assert Snapshot.model_validate_json(await page.recv()).board == hud.board


# Examples go over sockets, so their time varies more than the default deadline allows.
@given(writes())
@settings(deadline=None)
async def test_page_gets_the_board_after_each_write_that_changes_it(
    page: ClientConnection, agent: Client[Any], hud: Hud, writes: list[list[TBody]]
) -> None:
    """Assemble: a page on the app.
    Act: the agent writes each batch of actions.
    Assert: after each write that changes the board, the page gets the board."""
    async with asyncio.timeout(5):
        for batch in writes:
            before = hud.board
            await agent.call_tool("write", {"actions": as_json(*batch)}, raise_on_error=False)
            if hud.board != before:
                assert Snapshot.model_validate_json(await page.recv()).board == hud.board


@given(card_ids(), mds(), action_ids(), st.data())
@settings(deadline=None)
async def test_a_page_action_reaches_the_board_and_each_agent_or_is_rejected(
    page: ClientConnection,
    listeners: list[ClientConnection],
    agent: Client[Any],
    hud: Hud,
    card_id: str,
    md: str,
    action_id: str,
    data: st.DataObject,
) -> None:
    """Assemble: a card that the agent put, a page that got the board, and two agents' listeners.
    Act: the page asks for any action on the card or its parts.
    Assert: accepted, the page gets the board if it changed, and each listener gets the action; or rejected, and the board is as it was."""
    body = data.draw(bodies(st.just(card_id)))
    async with asyncio.timeout(5):
        before = hud.board
        await agent.call_tool("write", {"actions": as_json(put(card_id, md))})
        if hud.board != before:
            await page.recv()
        before = hud.board
        await page.send(Request(id=action_id, body=body).model_dump_json())
        answer, snapshots = await reply(page)
        match answer:
            case Accepted(id=accepted) if accepted == action_id:
                if hud.board != before and not snapshots:
                    snapshots.append(Snapshot.model_validate_json(await page.recv()))
                assert [snapshot.board for snapshot in snapshots] == ([] if hud.board == before else [hud.board])
                for listener in listeners:
                    assert Action.model_validate_json(await listener.recv()) == Action(
                        id=action_id, author=Author.user, body=body
                    )
            case Rejected(id=rejected) if rejected == action_id:
                assert (hud.board, snapshots) == (before, [])
            case other:
                pytest.fail(f"unexpected events {other}")


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


@given(st.lists(st.lists(st.tuples(action_ids(), messages()), min_size=1)))
@settings(deadline=None)
async def test_agent_gets_each_message_once_in_order(
    page: ClientConnection, listeners: list[ClientConnection], batches: list[list[tuple[str, str]]]
) -> None:
    """Assemble: a page and two agents' listeners on the app.
    Act: for each batch, the page says its messages.
    Assert: the page gets each message accepted, and each listener gets each message once, in the order sent."""
    async with asyncio.timeout(5):
        for batch in batches:
            for action_id, text in batch:
                await page.send(Request(id=action_id, body=say(text)).model_dump_json())
            assert [(await reply(page))[0].id for _ in batch] == [i for i, _ in batch]
            expected = [Action(id=i, author=Author.user, body=say(text)) for i, text in batch]
            for listener in listeners:
                assert [Action.model_validate_json(await listener.recv()) for _ in batch] == expected


@given(blanks())
async def test_a_message_needs_a_character_that_is_not_white_space(blank: str) -> None:
    """Assemble: text of white space only, or no text.
    Act: make a say action of it.
    Assert: ValidationError."""
    with pytest.raises(ValidationError):
        say(blank)
