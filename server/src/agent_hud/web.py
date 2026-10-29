import asyncio
import logging
import signal
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from time import monotonic
from typing import Annotated

from fastapi import Depends, FastAPI, Query, WebSocket, WebSocketException, status
from fastapi.staticfiles import StaticFiles
from mcp.server.subscriptions import InMemorySubscriptionBus, ResourceUpdated
from sqlalchemy import Engine
from sqlalchemy.orm import Session
from starlette.datastructures import Headers
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from agent_hud.boards import BoardSummary, TBoardName
from agent_hud.database import open_database
from agent_hud.deps import AgentOriginDep, PageOriginDep, token_dep
from agent_hud.exchange import Exchange, Monitor, act_on_board, summarize_boards
from agent_hud.frames import split_into_frames
from agent_hud.models.actions import Action, Author
from agent_hud.models.events import Accepted, EventKind, Rejected, Request, Turn
from agent_hud.queries.boards import check_board_exists, commit_board_state, load_board_state
from agent_hud.server import build_mcp_server, make_board_uri
from agent_hud.settings import get_settings


async def send_turn(websocket: WebSocket, turn: Turn, chars: int, gap: float) -> None:
    """
    Send the turn as its frames of at most the chars, with the gap in seconds between the frames, so that the monitor
    shows each frame as an event of its own.
    """
    for n, frame in enumerate(split_into_frames(turn, chars)):
        if n:
            await asyncio.sleep(gap)
        await websocket.send_text(frame)


class Bearer:
    """The app behind it, for requests that carry the token as a bearer token; 401 for the rest."""

    def __init__(self, app: ASGIApp, token: str) -> None:
        self.app = app
        self.token = token

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and Headers(scope=scope).get("authorization") != f"Bearer {self.token}":
            reply = PlainTextResponse("AGENT_HUD_TOKEN is set, so /mcp/ needs it as a bearer token", status_code=401)
            await reply(scope, receive, send)
            return
        await self.app(scope, receive, send)


class Activity:
    """
    When the app last served a request or closed a socket, how many sockets are open, and an event set on each, for
    the idle shutdown.
    """

    def __init__(self) -> None:
        self.last = monotonic()
        self.sockets = 0
        self.changed = asyncio.Event()

    def note(self, sockets: int = 0) -> None:
        """A request, or a socket that opened (1) or closed (-1), now."""
        self.last = monotonic()
        self.sockets += sockets
        self.changed.set()

    def idle_for(self) -> float:
        """How long the app has been idle: 0 while a page or a monitor is connected."""
        return 0 if self.sockets > 0 else monotonic() - self.last


class Watched:
    """The app behind it, with each request and socket noted in the activity."""

    def __init__(self, app: ASGIApp, activity: Activity) -> None:
        self.app = app
        self.activity = activity

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "lifespan":
            await self.app(scope, receive, send)
            return
        socket = scope["type"] == "websocket"
        self.activity.note(1 if socket else 0)
        try:
            await self.app(scope, receive, send)
        finally:
            self.activity.note(-1 if socket else 0)


def stop_process() -> None:
    """Stop the server as the hook does: uvicorn takes the signal and shuts down."""
    signal.raise_signal(signal.SIGTERM)


async def stop_when_idle(activity: Activity, after: float, stop: Callable[[], None]) -> None:
    """Call stop once the app has been idle for the seconds: no page or monitor connected, and no request."""
    while (idle := activity.idle_for()) < after:
        activity.changed.clear()
        with suppress(TimeoutError):
            async with asyncio.timeout(after - idle):
                await activity.changed.wait()
    logging.getLogger("agent_hud").info("idle for %.0f s with no page, monitor or request: stopping", after)
    stop()


def keep_token(token: str, state_dir: Path) -> None:
    """Write the token to the state dir, readable by the user only, so that they can open the page without the agent."""
    path = state_dir / "token"
    state_dir.mkdir(parents=True, exist_ok=True)
    path.touch(mode=0o600)
    path.chmod(0o600)
    path.write_text(token)


def create_app(engine: Engine, exchanges: dict[TBoardName, Exchange], stop: Callable[[], None]) -> FastAPI:
    """
    MCP for the agent at /mcp/, the board websocket at /ws, the list of boards at /boards and the built UI at /, on
    the boards in the database; exchanges holds the live exchange of each board in use.
    The agent's tools name their board in an argument, and the sockets in the board query parameter.
    The sockets and /boards need the socket token as a query parameter; /mcp/ needs the token as a bearer token when
    the settings give one. After the settings' idle seconds with no page or monitor connected and no request, the app
    calls stop.
    """
    settings = get_settings()
    keep_token(settings.socket_token, settings.state_dir)
    bus = InMemorySubscriptionBus()
    mcp_app = build_mcp_server(settings, engine, exchanges, bus).http_app(path="/")
    activity = Activity()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        """The MCP session manager and the idle watch while the app runs."""
        watch = (
            asyncio.create_task(stop_when_idle(activity, settings.idle_seconds, stop))
            if settings.idle_seconds > 0
            else None
        )
        try:
            async with mcp_app.lifespan(app):
                yield
        finally:
            if watch is not None:
                watch.cancel()

    def require_exchange(board: Annotated[TBoardName, Query()]) -> Exchange:
        """
        Find the exchange of the board that the socket's board query parameter names, and make it on first use.
        A policy violation when no board has the name.
        """
        with Session(engine) as session:
            if not check_board_exists(session, board):
                raise WebSocketException(status.WS_1008_POLICY_VIOLATION, f"no board '{board}'")
        return exchanges.setdefault(board, Exchange(board))

    app = FastAPI(lifespan=lifespan)
    # A DNS rebinding page sends its own name as Host, which passes the origin check.
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])
    app.add_middleware(Watched, activity=activity)
    with_token = token_dep(settings.socket_token)

    @app.get("/health")
    def health() -> dict[str, str]:
        """The app, its version and the build fingerprint it was started with, for the hook that starts it: any other answer on the port is another program."""
        return {"app": "agent-hud", "version": version("agent-hud"), "build": settings.build}

    @app.get("/boards", dependencies=[with_token])
    async def board_summaries() -> list[BoardSummary]:
        """Each board with its card count and agent state, for the page's list; 403 without the token as a query parameter."""
        with Session(engine) as session:
            return summarize_boards(session, exchanges)

    @app.websocket("/ws", dependencies=[PageOriginDep, with_token])
    async def page(websocket: WebSocket, exchange: Annotated[Exchange, Depends(require_exchange)]) -> None:
        """Send the board's snapshot on connect and after each change, and act for the user, until the page disconnects."""

        async def send_snapshots() -> None:
            """Load the board's state on connect and after each change, and send its snapshot when it differs."""
            last = None
            async for _ in exchange.watch_changes():
                with Session(engine) as session:
                    snapshot = exchange.take_snapshot(load_board_state(session, exchange.name))
                if snapshot != last:
                    last = snapshot
                    await websocket.send_text(snapshot.model_dump_json())

        await websocket.accept()
        async with asyncio.TaskGroup() as tg:
            sender = tg.create_task(send_snapshots())
            async for text in websocket.iter_text():
                request = Request.model_validate_json(text)
                action = Action(id=request.id, author=Author.user, body=request.body, at=datetime.now(UTC))
                try:
                    with Session(engine) as session:
                        act_on_board(session, exchange, [action])
                except ValueError as error:
                    reply = Rejected(kind=EventKind.rejected, id=request.id, reason=str(error)).model_dump_json()
                else:
                    reply = Accepted(kind=EventKind.accepted, id=request.id).model_dump_json()
                    await bus.publish(ResourceUpdated(uri=make_board_uri(exchange.name)))
                await websocket.send_text(reply)
            sender.cancel()

    @app.websocket("/agent", dependencies=[AgentOriginDep, with_token])
    async def agent(websocket: WebSocket, exchange: Annotated[Exchange, Depends(require_exchange)]) -> None:
        """Send each of the user's turns on the board to this agent's monitor, as frames of lines, until it disconnects."""

        async def deliver_turns(monitor: Monitor) -> None:
            """
            Load the board's state on connect and after each change, and send each sent turn not yet delivered to the
            monitor; then mark it delivered, so that a turn whose send fails comes again, and remove the turns that every
            open monitor has.
            """
            async for _ in exchange.watch_changes():
                with Session(engine) as session:
                    state = load_board_state(session, exchange.name)
                for turn in [turn for turn in state.sent_turns if turn.id not in monitor.delivered]:
                    await send_turn(websocket, turn, settings.monitor_chars, settings.monitor_gap)
                    exchange.mark_delivered(monitor, turn)
                    with Session(engine) as session:
                        state = load_board_state(session, exchange.name)
                        commit_board_state(
                            session, exchange.name, state.remove_turns(exchange.find_turns_delivered_to_all(state))
                        )

        await websocket.accept()
        with exchange.open_monitor() as monitor:
            async with asyncio.TaskGroup() as tg:
                sender = tg.create_task(deliver_turns(monitor))
                # The monitor sends nothing, so this returns when it disconnects.
                await websocket.receive()
                sender.cancel()

    app.mount("/mcp", mcp_app if settings.token is None else Bearer(mcp_app, settings.token))
    app.mount("/", StaticFiles(directory=settings.static_dir, html=True))
    return app


def app_factory() -> FastAPI:
    """Make the app as uvicorn serves it: on the database in the data folder, with no live exchange yet, and the process stops when idle."""
    engine = open_database(get_settings().data_dir / "agent-hud.db")
    return create_app(engine, {}, stop_process)
