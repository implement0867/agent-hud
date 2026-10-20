import asyncio

from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from agent_hud.deps import SameOriginDep, StoreDep
from agent_hud.models.events import BoardEvent, EventKind, SendEvent
from agent_hud.server import build
from agent_hud.settings import get_settings
from agent_hud.store import BoardStore


async def send_boards(websocket: WebSocket, store: BoardStore) -> None:
    async for board in store.watch():
        await websocket.send_text(BoardEvent(kind=EventKind.board, board=board).model_dump_json())


def create_app() -> FastAPI:
    """MCP for the agent at /mcp/, the board websocket at /ws, and the built UI at /."""
    mcp_app = build().http_app(path="/")
    app = FastAPI(lifespan=mcp_app.lifespan)
    # A DNS rebinding page sends its own name as Host, which passes the origin check.
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])

    @app.websocket("/ws", dependencies=[SameOriginDep])
    async def board_updates(websocket: WebSocket, store: StoreDep) -> None:
        """Send the board on connect and after each change, and take the page's messages, until it disconnects."""
        await websocket.accept()
        async with asyncio.TaskGroup() as tg:
            sender = tg.create_task(send_boards(websocket, store))
            async for text in websocket.iter_text():
                store.add_message(SendEvent.model_validate_json(text).message)
            sender.cancel()

    app.mount("/mcp", mcp_app)
    app.mount("/", StaticFiles(directory=get_settings().static_dir, html=True))
    return app
