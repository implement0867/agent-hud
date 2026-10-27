import asyncio
import logging
import signal
from collections.abc import AsyncGenerator, AsyncIterator, Callable
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from time import monotonic
from typing import Annotated

from fastapi import Depends, FastAPI, Query, WebSocket, WebSocketException, status
from fastapi.staticfiles import StaticFiles
from mcp.server.subscriptions import InMemorySubscriptionBus, ResourceUpdated
from starlette.datastructures import Headers
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from agent_hud.boards import BoardSummary, TBoardName, board_names, open_exchange, summarize
from agent_hud.deps import AgentOriginDep, PageOriginDep, token_dep
from agent_hud.exchange import Exchange
from agent_hud.frames import split_into_frames
from agent_hud.models.actions import Action, Author
from agent_hud.models.base import Model
from agent_hud.models.events import Accepted, EventKind, Rejected, Request, Turn
from agent_hud.server import board_uri, build_mcp_server
from agent_hud.settings import get_settings


async def send_each(websocket: WebSocket, events: AsyncIterator[Model]) -> None:
    """Send each event as JSON text as it comes."""
    async for event in events:
        await websocket.send_text(event.model_dump_json())


async def send_turns(websocket: WebSocket, turns: AsyncIterator[Turn], chars: int, gap: float) -> None:
    """
    Send each turn as its frames of at most the chars, with the gap in seconds between the frames of one turn, so that
    the monitor shows each frame as an event of its own.
    """
    async for turn in turns:
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
    """Stop the server as the hook does: uvicorn takes the signal and shuts down, so the boards compact and close."""
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


def create_app(exchanges: dict[TBoardName, Exchange], stop: Callable[[], None]) -> FastAPI:
    """
    MCP for the agent at /mcp/, the board websocket at /ws, the list of boards at /boards and the built UI at /, on
    the boards in the settings' boards dir; exchanges holds each board that is open.
    The agent's tools name their board in an argument, and the sockets in the board query parameter.
    The sockets and /boards need the socket token as a query parameter; /mcp/ needs the token as a bearer token when
    the settings give one. After the settings' idle seconds with no page or monitor connected and no request, the app
    calls stop. RuntimeError when another process holds a board's file, as a second uvicorn worker would.
    """
    settings = get_settings()
    keep_token(settings.socket_token, settings.state_dir)
    bus = InMemorySubscriptionBus()
    mcp_app = build_mcp_server(settings, exchanges, bus).http_app(path="/")
    activity = Activity()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        """The MCP session manager and the idle watch while the app runs, and each board's file compacted and let go on shutdown."""
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
            for exchange in exchanges.values():
                exchange.compact()
                exchange.close()

    async def require_board(board: Annotated[TBoardName, Query()]) -> tuple[TBoardName, Exchange]:
        """
        The board that the socket's board query parameter names, and its exchange. A policy violation when there is none.
        Async, so that the exchange's SQLite file opens on the event loop's thread, which uses it.
        """
        try:
            return board, open_exchange(exchanges, settings.boards_dir, board)
        except ValueError as error:
            raise WebSocketException(status.WS_1008_POLICY_VIOLATION, str(error)) from error

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
        return [
            summarize(name, open_exchange(exchanges, settings.boards_dir, name))
            for name in board_names(settings.boards_dir)
        ]

    @app.websocket("/ws", dependencies=[PageOriginDep, with_token])
    async def page(websocket: WebSocket, board: Annotated[tuple[TBoardName, Exchange], Depends(require_board)]) -> None:
        """Send the board's snapshot on connect and after each change, and act for the user, until the page disconnects."""
        name, exchange = board
        await websocket.accept()
        async with asyncio.TaskGroup() as tg:
            sender = tg.create_task(send_each(websocket, exchange.snapshots()))
            async for text in websocket.iter_text():
                request = Request.model_validate_json(text)
                try:
                    exchange.act([Action(id=request.id, author=Author.user, body=request.body, at=datetime.now(UTC))])
                except ValueError as error:
                    reply = Rejected(kind=EventKind.rejected, id=request.id, reason=str(error)).model_dump_json()
                else:
                    reply = Accepted(kind=EventKind.accepted, id=request.id).model_dump_json()
                    await bus.publish(ResourceUpdated(uri=board_uri(name)))
                await websocket.send_text(reply)
            sender.cancel()

    @app.websocket("/agent", dependencies=[AgentOriginDep, with_token])
    async def agent(
        websocket: WebSocket, board: Annotated[tuple[TBoardName, Exchange], Depends(require_board)]
    ) -> None:
        """Send each of the user's turns on the board to this agent's monitor, as frames of lines, until it disconnects."""
        _, exchange = board
        await websocket.accept()
        with exchange.monitor():
            async with asyncio.TaskGroup() as tg:
                sender = tg.create_task(
                    send_turns(websocket, exchange.user_turns(), settings.monitor_chars, settings.monitor_gap)
                )
                # The monitor sends nothing, so this returns when it disconnects.
                await websocket.receive()
                sender.cancel()

    app.mount("/mcp", mcp_app if settings.token is None else Bearer(mcp_app, settings.token))
    app.mount("/", StaticFiles(directory=settings.static_dir, html=True))
    return app


def app_factory() -> FastAPI:
    """The app as uvicorn serves it: no board open yet, and the process stops when idle."""
    return create_app({}, stop_process)
