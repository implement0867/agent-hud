import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from secrets import token_urlsafe
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketException, status
from fastapi import Request as HttpRequest
from fastapi.staticfiles import StaticFiles
from starlette.datastructures import Headers
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from agent_hud.boards import BoardInfo, Huds, TBoardId
from agent_hud.deps import AgentOriginDep, PageOriginDep, token_dep
from agent_hud.hud import Hud
from agent_hud.models.actions import Action, Author
from agent_hud.models.events import Accepted, EventKind, Rejected, Request
from agent_hud.server import build
from agent_hud.settings import get_settings


async def send_snapshots(websocket: WebSocket, hud: Hud) -> None:
    async for snapshot in hud.snapshots():
        await websocket.send_text(snapshot.model_dump_json())


async def send_user_turns(websocket: WebSocket, hud: Hud) -> None:
    async for turn in hud.user_turns():
        await websocket.send_text(turn.model_dump_json())


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


def keep_token(token: str, state_dir: Path) -> None:
    """Write the token to the state dir, readable by the user only, so that they can open the page without the agent."""
    path = state_dir / "token"
    state_dir.mkdir(parents=True, exist_ok=True)
    path.touch(mode=0o600)
    path.chmod(0o600)
    path.write_text(token)


def create_app(hud: Hud | None = None) -> FastAPI:
    """
    MCP for the agent at /mcp/, the board websocket at /ws, the list of boards at /boards and the built UI at /, on
    the boards in the settings' directory, with the hud as the shared board when one is given. The agent's requests
    name their board in the X-Agent-Hud-Board header, and the sockets in the board query parameter.
    The sockets and /boards need the token as a query parameter; /mcp/ needs it as a bearer token when the settings give one.
    RuntimeError when another process holds a board's file, as a second uvicorn worker would.
    """
    settings = get_settings()
    huds = Huds(settings.board_files, shared=hud)
    token = settings.token or token_urlsafe(32)
    keep_token(token, settings.state_dir)
    mcp_app = build(huds, token).http_app(path="/")

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        """The MCP session manager while the app runs, and each board's file compacted and let go on shutdown."""
        try:
            async with mcp_app.lifespan(app):
                yield
        finally:
            huds.compact()
            huds.close()

    def require_board(websocket: WebSocket) -> Hud:
        """The hud of the board that the socket's board query parameter names; the shared board without one."""
        board: TBoardId = websocket.query_params.get("board", Huds.shared)
        hud = huds.get(board)
        if hud is None:
            raise WebSocketException(status.WS_1008_POLICY_VIOLATION, f"no board '{board}'")
        return hud

    app = FastAPI(lifespan=lifespan)
    # A DNS rebinding page sends its own name as Host, which passes the origin check.
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])
    with_token = token_dep(token)

    @app.get("/health")
    def health() -> dict[str, str]:
        """The app, its version and the build fingerprint it was started with, for the hook that starts it: any other answer on the port is another program."""
        return {"app": "agent-hud", "version": version("agent-hud"), "build": settings.build}

    @app.get("/boards")
    def boards(request: HttpRequest) -> list[BoardInfo]:
        """Each board with its card count and agent state, for the page's list; 403 without the token as a query parameter."""
        if request.query_params.get("token") != token:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "the token is missing or wrong")
        return huds.boards()

    @app.websocket("/ws", dependencies=[PageOriginDep, with_token])
    async def page(websocket: WebSocket, hud: Annotated[Hud, Depends(require_board)]) -> None:
        """Send the board's snapshot on connect and after each change, and act for the user, until the page disconnects."""
        await websocket.accept()
        async with asyncio.TaskGroup() as tg:
            sender = tg.create_task(send_snapshots(websocket, hud))
            async for text in websocket.iter_text():
                request = Request.model_validate_json(text)
                try:
                    hud.act([Action(id=request.id, author=Author.user, body=request.body, at=datetime.now(UTC))])
                except ValueError as error:
                    reply = Rejected(kind=EventKind.rejected, id=request.id, reason=str(error)).model_dump_json()
                else:
                    reply = Accepted(kind=EventKind.accepted, id=request.id).model_dump_json()
                await websocket.send_text(reply)
            sender.cancel()

    @app.websocket("/agent", dependencies=[AgentOriginDep, with_token])
    async def agent(websocket: WebSocket, hud: Annotated[Hud, Depends(require_board)]) -> None:
        """Send each of the user's turns on the board to this agent's monitor, until it disconnects."""
        await websocket.accept()
        with hud.monitor():
            async with asyncio.TaskGroup() as tg:
                sender = tg.create_task(send_user_turns(websocket, hud))
                # The monitor sends nothing, so this returns when it disconnects.
                await websocket.receive()
                sender.cancel()

    app.mount("/mcp", mcp_app if settings.token is None else Bearer(mcp_app, settings.token))
    app.mount("/", StaticFiles(directory=settings.static_dir, html=True))
    return app
