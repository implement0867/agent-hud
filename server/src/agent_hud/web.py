import asyncio

from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from agent_hud.deps import HudDep, SameOriginDep
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


def create_app() -> FastAPI:
    """MCP for the agent at /mcp/, the board websocket at /ws, and the built UI at /."""
    mcp_app = build().http_app(path="/")
    app = FastAPI(lifespan=mcp_app.lifespan)
    # A DNS rebinding page sends its own name as Host, which passes the origin check.
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])

    @app.websocket("/ws", dependencies=[SameOriginDep])
    async def page(websocket: WebSocket, hud: HudDep) -> None:
        """Send the snapshot on connect and after each change, and act for the user, until the page disconnects."""
        await websocket.accept()
        async with asyncio.TaskGroup() as tg:
            sender = tg.create_task(send_snapshots(websocket, hud))
            async for text in websocket.iter_text():
                request = Request.model_validate_json(text)
                try:
                    hud.act([Action(id=request.id, author=Author.user, body=request.body)])
                except ValueError as error:
                    reply = Rejected(kind=EventKind.rejected, id=request.id, reason=str(error)).model_dump_json()
                else:
                    reply = Accepted(kind=EventKind.accepted, id=request.id).model_dump_json()
                await websocket.send_text(reply)
            sender.cancel()

    @app.websocket("/agent", dependencies=[SameOriginDep])
    async def agent(websocket: WebSocket, hud: HudDep) -> None:
        """Send each of the user's turns to this agent's monitor, until it disconnects."""
        await websocket.accept()
        with hud.monitor():
            async with asyncio.TaskGroup() as tg:
                sender = tg.create_task(send_user_turns(websocket, hud))
                # The monitor sends nothing, so this returns when it disconnects.
                await websocket.receive()
                sender.cancel()

    app.mount("/mcp", mcp_app)
    app.mount("/", StaticFiles(directory=get_settings().static_dir, html=True))
    return app
