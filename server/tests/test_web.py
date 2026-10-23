import asyncio
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack
from importlib.metadata import version
from json import load
from pathlib import Path
from typing import Any
from urllib.request import urlopen

import pytest
import pytest_asyncio
from fastmcp import Client
from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.provisional import domains
from mcp.shared.exceptions import MCPError
from pydantic import ValidationError
from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import InvalidStatus

from agent_hud.hud import Hud
from agent_hud.models.actions import ActionKind, TBody
from agent_hud.models.events import Accepted, Rejected, Snapshot, Turn
from agent_hud.server import build
from agent_hud.settings import get_settings
from agent_hud.web import create_app
from tests.conversation import TOKEN, User, open_page, serve
from tests.factories import as_json, put, say
from tests.strategies import blanks, bodies, card_ids, mds, messages

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


@pytest.fixture(scope="module")
def hud() -> Hud:
    """A new hud for the module, for the app and the agent."""
    return Hud()


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def address(static_dir: Path, hud: Hud) -> AsyncIterator[tuple[str, int]]:
    """Host and port of the app on the module's hud."""
    async with serve(hud, static_dir) as address:
        yield address


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def user(address: tuple[str, int], hud: Hud) -> AsyncIterator[User]:
    """A page from the app's origin."""
    async with open_page(address) as user:
        yield user


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def listeners(address: tuple[str, int], hud: Hud) -> AsyncIterator[list[ClientConnection]]:
    """Two agents' sockets for the user's actions, at the URL that the listen tool returns."""
    host, port = address
    async with Client(f"http://{host}:{port}/mcp/", auth=TOKEN) as remote:
        url = (await remote.call_tool("listen", {})).data
    async with AsyncExitStack() as stack:
        yield [await stack.enter_async_context(connect(url, proxy=None)) for _ in range(2)]


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def agent(hud: Hud) -> AsyncIterator[Client[Any]]:
    """The MCP tools in memory, on the same hud as the app. MCP over HTTP is slower per call."""
    async with Client(build(hud)) as client:
        yield client


async def test_app_serves_the_tools_over_http(address: tuple[str, int], agent: Client[Any]) -> None:
    """Assemble: the app, and the MCP tools in memory.
    Act: list the tools over HTTP at /mcp/.
    Assert: the same tools as in memory."""
    host, port = address
    async with Client(f"http://{host}:{port}/mcp/", auth=TOKEN) as remote:
        assert await remote.list_tools() == await agent.list_tools()


async def test_tools_need_the_token_when_the_settings_give_one(address: tuple[str, int]) -> None:
    """Assemble: the app with a token from the settings.
    Act: connect to /mcp/ without it.
    Assert: the server answers with an error and no tools."""
    host, port = address
    with pytest.raises(MCPError):
        async with Client(f"http://{host}:{port}/mcp/") as remote:
            await remote.list_tools()


async def test_the_token_is_kept_in_the_state_dir_for_the_user_only(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Assemble: settings with a state dir and no token.
    Act: create the app.
    Assert: the token file in the state dir has the token of the URL that listen returns, readable by the user only."""
    monkeypatch.setenv("AGENT_HUD_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.delenv("AGENT_HUD_TOKEN", raising=False)
    get_settings.cache_clear()
    try:
        create_app(Hud())
    finally:
        get_settings.cache_clear()
    path = tmp_path / "state" / "token"
    assert path.stat().st_mode & 0o777 == 0o600
    assert len(path.read_text()) >= 32


async def test_health_names_the_app_and_its_version(address: tuple[str, int]) -> None:
    """Assemble: the app.
    Act: get /health.
    Assert: the app's name and the package version, for the hook to tell the app from another program on the port."""
    host, port = address
    with await asyncio.to_thread(urlopen, f"http://{host}:{port}/health") as answer:
        assert (answer.status, load(answer)) == (200, {"app": "agent-hud", "version": version("agent-hud")})


async def test_page_gets_the_board_on_connect(address: tuple[str, int], hud: Hud) -> None:
    """Assemble: the app.
    Act: open a page from the app's origin.
    Assert: the first event carries the board."""
    host, port = address
    async with connect(f"ws://{host}:{port}/ws?token={TOKEN}", origin=f"http://{host}:{port}", proxy=None) as page:
        assert Snapshot.model_validate_json(await page.recv()).board == hud.board


@pytest.mark.parametrize("path", ["/ws", "/agent"])
@pytest.mark.parametrize("query", ["", "?token=", "?token=other"])
async def test_sockets_need_the_token(address: tuple[str, int], path: str, query: str) -> None:
    """Assemble: the app.
    Act: open the websocket from the app's origin without the token, or with another.
    Assert: the handshake fails."""
    host, port = address
    with pytest.raises(InvalidStatus):
        await connect(f"ws://{host}:{port}{path}{query}", origin=f"http://{host}:{port}", proxy=None)


async def test_a_request_without_origin_is_not_the_page(address: tuple[str, int]) -> None:
    """Assemble: the app.
    Act: open /ws with the token and no Origin, as a local script does.
    Assert: the handshake fails, since the browser always sends the Origin."""
    host, port = address
    with pytest.raises(InvalidStatus):
        await connect(f"ws://{host}:{port}/ws?token={TOKEN}", proxy=None)


async def test_the_agent_socket_takes_the_token_without_origin(address: tuple[str, int]) -> None:
    """Assemble: the app.
    Act: open /agent with the token and no Origin, as the monitor does.
    Assert: the handshake succeeds."""
    host, port = address
    async with connect(f"ws://{host}:{port}/agent?token={TOKEN}", proxy=None):
        pass


# Examples go over sockets, so their time varies more than the default deadline allows.
@given(writes())
@settings(deadline=None)
async def test_page_gets_the_board_after_each_write(
    user: User, agent: Client[Any], hud: Hud, writes: list[list[TBody]]
) -> None:
    """Assemble: a page on the app.
    Act: the agent writes each batch of actions.
    Assert: after each write, the page shows the board."""
    for batch in writes:
        await agent.call_tool("write", {"actions": as_json(*batch)}, raise_on_error=False)
        assert await user.sees(hud.board) == hud.board


@given(card_ids(), mds(), st.data())
@settings(deadline=None)
async def test_a_page_action_reaches_the_board_and_each_agent_on_send_or_is_rejected(
    user: User,
    listeners: list[ClientConnection],
    agent: Client[Any],
    hud: Hud,
    card_id: str,
    md: str,
    data: st.DataObject,
) -> None:
    """Assemble: a card that the agent put, a page, and two agents' listeners.
    Act: the page asks for any action on the card or its parts, then sends if the action did not end the turn.
    Assert: accepted, the page shows the board and each listener gets a turn of the action; or rejected, and the board is as it was."""
    body = data.draw(bodies(st.just(card_id)))
    await agent.call_tool("write", {"actions": as_json(put(card_id, md))})
    before = hud.board
    match await user.act(body):
        case Accepted(id=action_id):
            assert await user.sees(hud.board) == hud.board
            if not hud.log.actions[-1].ends_turn:
                await user.send()
            heard = [] if body.kind is ActionKind.send else [action_id]
            for listener in listeners:
                turn = Turn.model_validate_json(await asyncio.wait_for(listener.recv(), 5))
                assert [action.id for action in turn.actions] == heard
        case Rejected():
            assert hud.board == before


@pytest.mark.parametrize("path", ["/ws", "/agent"])
@given(host_names())
@settings(deadline=None)
async def test_pages_of_other_sites_cannot_connect(address: tuple[str, int], path: str, domain: str) -> None:
    """Assemble: the app.
    Act: open the websocket with the Origin of another site.
    Assert: the handshake fails."""
    host, port = address
    with pytest.raises(InvalidStatus):
        await connect(f"ws://{host}:{port}{path}?token={TOKEN}", origin=f"http://{domain}", proxy=None)


@pytest.mark.parametrize("path", ["/ws", "/agent"])
@given(host_names())
@settings(deadline=None)
async def test_other_host_names_cannot_connect(address: tuple[str, int], path: str, domain: str) -> None:
    """Assemble: the app.
    Act: open the websocket by another host name with its own Origin, as a DNS rebinding page does.
    Assert: the handshake fails."""
    host, port = address
    with pytest.raises(InvalidStatus):
        await connect(
            f"ws://{domain}:{port}{path}?token={TOKEN}", host=host, origin=f"http://{domain}:{port}", proxy=None
        )


# Each message grows the module's board, which each snapshot carries, so the lists are short.
@given(st.lists(st.lists(messages(), min_size=1, max_size=5), max_size=5))
@settings(deadline=None, max_examples=25)
async def test_agent_gets_each_message_once_in_order(
    user: User, listeners: list[ClientConnection], batches: list[list[str]]
) -> None:
    """Assemble: a page and two agents' listeners on the app.
    Act: for each batch, the page says its messages.
    Assert: the page gets each message accepted, and each listener gets a turn of each message once, in the order sent."""
    for batch in batches:
        answers = [await user.act(say(text)) for text in batch]
        assert all(isinstance(answer, Accepted) for answer in answers)
        for listener in listeners:
            turns = [Turn.model_validate_json(await asyncio.wait_for(listener.recv(), 5)) for _ in batch]
            assert [[(a.id, a.body) for a in turn.actions] for turn in turns] == [
                [(answer.id, say(text))] for answer, text in zip(answers, batch, strict=True)
            ]


@given(blanks())
async def test_a_message_needs_a_character_that_is_not_white_space(blank: str) -> None:
    """Assemble: text of white space only, or no text.
    Act: make a say action of it.
    Assert: ValidationError."""
    with pytest.raises(ValidationError):
        say(blank)
