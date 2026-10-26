import asyncio
import itertools
import re
import shlex
import sys
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack
from importlib.metadata import version
from json import load
from pathlib import Path
from time import monotonic
from typing import Any, cast
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest
import pytest_asyncio
from fastapi import WebSocket
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.provisional import domains
from mcp.shared.exceptions import MCPError
from pydantic import ValidationError
from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import InvalidStatus

from agent_hud.boards import Huds
from agent_hud.frames import head_of, turn_of
from agent_hud.hud import Hud
from agent_hud.models.actions import Action, ActionKind, Author, TBody
from agent_hud.models.events import Accepted, AgentState, Rejected, Snapshot, Turn
from agent_hud.server import build
from agent_hud.settings import get_settings
from agent_hud.store import Store
from agent_hud.web import create_app, send_turns
from tests.conversation import TOKEN, User, listen_url, open_agent, open_page, receive_turn, serve
from tests.factories import as_json, comment, put, read_board, say, send
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
async def address(static_dir: Path, state_dir: Path, hud: Hud) -> AsyncIterator[tuple[str, int]]:
    """Host and port of the app on the module's hud."""
    async with serve(hud, static_dir, state_dir) as address:
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
        url = await listen_url(remote)
    async with AsyncExitStack() as stack:
        yield [await stack.enter_async_context(connect(url, proxy=None)) for _ in range(2)]


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def agent(hud: Hud) -> AsyncIterator[Client[Any]]:
    """The MCP tools in memory, on the same hud as the app. MCP over HTTP is slower per call."""
    async with Client(build(Huds(None, shared=hud))) as client:
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


async def test_the_app_compacts_the_state_file_on_shutdown(static_dir: Path, tmp_path: Path) -> None:
    """Assemble: a hud on a state file, with a card, a send that an agent took, and a comment the user has not sent.
    Act: serve the app on it, and stop it.
    Assert: the checkpoint holds the board at the start of the user's turn, the state file only the turn, and a new hud starts on it."""
    state_file = tmp_path / "board.db"
    hud = Hud(state_file)
    hud.act([Action(id="a", author=Author.agent, body=put("plan", "1. a"))])
    hud.act([Action(id="u", author=Author.user, body=send())])
    hud.act([Action(id="r", author=Author.user, body=comment("plan", "yes", "a"))])
    async with serve(hud, static_dir, tmp_path) as address, open_agent(address):
        pass
    store = Store(state_file)
    _, checkpoint, kept, _ = store.load()
    store.close()
    assert checkpoint.cards == hud.board.cards
    assert checkpoint.threads == {}
    assert [action.id for action in kept] == ["r"]
    again = Hud(state_file)
    assert again.board == hud.board
    again.close()


async def test_a_second_app_on_the_state_dir_does_not_start(static_dir: Path, tmp_path: Path) -> None:
    """Assemble: an app served on a state dir, with the shared board's file in its boards directory.
    Act: create an app from the settings on the same state dir, as a second uvicorn worker would.
    Assert: RuntimeError that names the shared board's file; and once the first app has stopped, the app starts."""
    shared = tmp_path / "boards" / "shared.db"
    async with serve(Hud(shared), static_dir, tmp_path):
        with pytest.MonkeyPatch.context() as env:
            env.setenv("AGENT_HUD_STATIC_DIR", str(static_dir))
            env.setenv("AGENT_HUD_STATE_DIR", str(tmp_path))
            get_settings.cache_clear()
            try:
                with pytest.raises(RuntimeError, match=re.escape(str(shared))):
                    create_app()
            finally:
                get_settings.cache_clear()
    async with serve(Hud(shared), static_dir, tmp_path) as address:
        host, port = address
        with await asyncio.to_thread(urlopen, f"http://{host}:{port}/health") as answer:
            assert answer.status == 200


def project_tools(address: tuple[str, int], project: str) -> StreamableHttpTransport:
    """The MCP tools over HTTP, with the project directory in the board header, as the plugin sends it."""
    host, port = address
    return StreamableHttpTransport(f"http://{host}:{port}/mcp/", headers={"X-Agent-Hud-Board": project}, auth=TOKEN)


async def test_each_project_has_its_own_board(address: tuple[str, int], hud: Hud) -> None:
    """Assemble: the app, whose shared board is the module's hud.
    Act: an agent whose requests name a project directory puts a card and listens; a page opens that board, and another the shared board; a second agent names another directory of the same name.
    Assert: the card is on the project's board alone, listen names the board in its URL and the id names the project, the second agent has a third board, the page of the project's board sees the card, and the shared board is as it was."""
    host, port = address
    async with Client(project_tools(address, "/home/me/work/agent-hud")) as remote:
        await remote.call_tool("write", {"actions": as_json(put("plan", "1. a"))})
        listening = (await remote.call_tool("listen", {})).structured_content
    assert listening is not None
    board = str(listening["board"])
    assert re.fullmatch(r"agent-hud-[0-9a-f]{6}", board)
    assert f"board={board}" in str(listening["url"]) and listening["monitors"] == 0
    assert "plan" not in hud.board.cards
    async with Client(project_tools(address, "/home/you/agent-hud")) as other:
        assert (await read_board(other)).cards == {}
        assert str((await other.call_tool("listen", {})).structured_content["board"]) not in {board, "shared"}  # type: ignore[index]
    origin = f"http://{host}:{port}"
    async with connect(f"ws://{host}:{port}/ws?token={TOKEN}&board={board}", origin=origin, proxy=None) as page:
        assert list(Snapshot.model_validate_json(await page.recv()).board.cards) == ["plan"]
    with await asyncio.to_thread(urlopen, f"http://{host}:{port}/boards?token={TOKEN}") as answer:
        boards = {entry["id"]: entry["cards"] for entry in load(answer)}
    assert boards["shared"] == len(hud.board.cards) and boards[board] == 1 and len(boards) == 3


async def test_a_monitor_on_one_board_counts_for_that_board_alone(address: tuple[str, int], hud: Hud) -> None:
    """Assemble: the app, and the id of a project's board from listen.
    Act: open a monitor on the project's board.
    Assert: the project's board says an agent waits and the shared board says none; and a socket on a board that there is not fails."""
    host, port = address
    async with Client(project_tools(address, "/home/me/work/other")) as remote:
        listening = (await remote.call_tool("listen", {})).structured_content
    assert listening is not None
    async with connect(str(listening["url"]), proxy=None):
        await asyncio.sleep(0.1)
        with await asyncio.to_thread(urlopen, f"http://{host}:{port}/boards?token={TOKEN}") as answer:
            agents = {entry["id"]: entry["agent"] for entry in load(answer)}
        assert agents[str(listening["board"])] == AgentState.waiting and agents["shared"] == hud.snapshot().agent
    with pytest.raises(InvalidStatus):
        await connect(f"ws://{host}:{port}/agent?token={TOKEN}&board=nowhere", proxy=None)
    with pytest.raises(HTTPError, match="403"):
        await asyncio.to_thread(urlopen, f"http://{host}:{port}/boards")


async def test_the_turns_command_prints_each_turn_as_a_line(address: tuple[str, int]) -> None:
    """Assemble: the app, and the command that listen returns, run as a monitor that takes a command would run it.
    Act: the user says a message.
    Assert: the command prints the turn as one line, and listen's command runs agent-hud-turns on its URL."""
    host, port = address
    async with Client(f"http://{host}:{port}/mcp/", auth=TOKEN) as tools:
        listening = (await tools.call_tool("listen", {})).structured_content
    assert listening is not None
    assert listening["command"].endswith(f"agent-hud-turns {shlex.quote(listening['url'])}")
    turns = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "agent_hud.turns", listening["url"], stdout=asyncio.subprocess.PIPE
    )
    assert turns.stdout is not None
    try:
        async with open_page(address) as user:
            await user.notes(lambda snapshot: snapshot.agent is AgentState.waiting)
            assert isinstance(await user.act(say("hello")), Accepted)
            async with asyncio.timeout(5):
                head = await turns.stdout.readline()
                lines = [await turns.stdout.readline() for _ in range(head_of(head.decode()).actions)]
        assert turn_of(["".join([head.decode(), *(line.decode() for line in lines)]).rstrip("\n")]).actions == (
            say("hello"),
        )
    finally:
        turns.terminate()
        await turns.wait()


async def test_health_names_the_app_and_its_version(address: tuple[str, int]) -> None:
    """Assemble: the app.
    Act: get /health.
    Assert: the app's name, the package version and the build fingerprint from the settings, for the hook to tell the app from another program on the port."""
    host, port = address
    with await asyncio.to_thread(urlopen, f"http://{host}:{port}/health") as answer:
        assert (answer.status, load(answer)) == (
            200,
            {"app": "agent-hud", "version": version("agent-hud"), "build": ""},
        )


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
    Act: the page asks for any action on the card or its words, then sends if the action did not end the turn.
    Assert: accepted, the page shows the board and each listener gets a turn of what the page listed as pending; or rejected, and the board is as it was."""
    body = data.draw(bodies(st.just(card_id)))
    await agent.call_tool("write", {"actions": as_json(put(card_id, md))})
    before = hud.board
    pending = [heard.body for heard in hud.snapshot().pending]
    match await user.act(body):
        case Accepted():
            assert await user.sees(hud.board) == hud.board
            if not hud.log.actions[-1].ends_turn:
                heard = [heard.body for heard in hud.snapshot().pending]
                await user.send()
            else:
                heard = [*pending, body] if body.kind is ActionKind.say else pending
            for listener in listeners:
                assert list((await receive_turn(listener)).actions) == heard
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
            turns = [await receive_turn(listener) for _ in batch]
            assert [(turn.id, list(turn.actions)) for turn in turns] == [
                (answer.id, [say(text)]) for answer, text in zip(answers, batch, strict=True)
            ]


@given(blanks())
async def test_a_message_needs_a_character_that_is_not_white_space(blank: str) -> None:
    """Assemble: text of white space only, or no text.
    Act: make a say action of it.
    Assert: ValidationError."""
    with pytest.raises(ValidationError):
        say(blank)


async def test_a_long_turn_reaches_the_monitor_as_frames_of_the_size(static_dir: Path, tmp_path: Path) -> None:
    """Assemble: an app whose monitor frames hold 300 characters, with a list of eight items on its board.
    Act: the user comments on each item and sends.
    Assert: the monitor gets several frames, each within the size, whose turn is the comments."""
    hud = Hud()
    texts = [f"step {n} of the plan, with words that fill the line" for n in range(1, 9)]
    async with (
        serve(hud, static_dir, tmp_path, monitor_chars=300) as address,
        open_agent(address) as agent,
        open_page(address) as user,
    ):
        await agent.write(put("plan", "\n".join(f"- {text}" for text in texts)))
        comments = [comment("plan", "why this step?", text) for text in texts]
        for body in comments:
            assert isinstance(await user.act(body), Accepted)
        await user.send()
        frames: list[str] = []
        async with asyncio.timeout(10):
            while not frames or (head := head_of(frames[-1])).of is None or head.frame != head.of:
                frames.append(str(await agent.monitor.recv()))
    assert len(frames) > 1
    assert all(len(frame) <= 300 for frame in frames)
    turn = turn_of(frames)
    assert list(turn.actions) == comments


class Recorder:
    """A websocket that records when each text was sent, for the sender of turns."""

    def __init__(self) -> None:
        self.sent: list[tuple[float, str]] = []

    async def send_text(self, text: str) -> None:
        self.sent.append((monotonic(), text))


async def test_the_sender_leaves_the_gap_between_the_frames_of_a_turn_and_none_between_turns() -> None:
    """Assemble: two turns, of which the first takes three frames of 200 characters and the second one.
    Act: send them with a gap of 0.2 s.
    Assert: the frames of the first turn go at least the gap apart, and the second turn's frame follows the last at once."""
    first = Turn(id="one", actions=tuple(say(f"message {n} of the first turn, long enough") for n in range(6)))
    second = Turn(id="two", actions=(say("hi"),))

    async def turns() -> AsyncIterator[Turn]:
        yield first
        yield second

    recorder = Recorder()
    await send_turns(cast(WebSocket, recorder), turns(), 200, 0.2)
    assert [head_of(text).of for _, text in recorder.sent] == [3, 3, 3, None]
    gaps = [later - earlier for (earlier, _), (later, _) in itertools.pairwise(recorder.sent)]
    assert all(gap >= 0.19 for gap in gaps[:2]) and gaps[2] < 0.1, gaps
