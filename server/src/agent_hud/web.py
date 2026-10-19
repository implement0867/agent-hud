import asyncio
from pathlib import Path

from fastapi import Depends, FastAPI, WebSocket, WebSocketException, status
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from agent_hud.changes import Changes
from agent_hud.models.board import Board


def require_same_origin(websocket: WebSocket) -> None:
    """Websockets skip CORS, so any site open in the browser could read the board without this check."""
    origin = websocket.headers.get("origin")
    if origin not in (None, f"http://{websocket.headers['host']}"):
        raise WebSocketException(status.WS_1008_POLICY_VIOLATION, f"origin {origin} is not allowed")


def create_app(board: Board, changes: Changes, static_dir: Path) -> FastAPI:
    app = FastAPI()
    # A DNS rebinding page sends its own name as Host, which passes the origin check.
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])

    async def send_boards(websocket: WebSocket) -> None:
        while True:
            changed = changes.next
            await websocket.send_text(board.model_dump_json())
            await changed.wait()

    @app.websocket("/ws", dependencies=[Depends(require_same_origin)])
    async def board_updates(websocket: WebSocket) -> None:
        """Send the board on connect and after each change, until the page disconnects."""
        await websocket.accept()
        async with asyncio.TaskGroup() as tg:
            sender = tg.create_task(send_boards(websocket))
            # The page sends nothing yet, so the first message is its disconnect.
            await websocket.receive()
            sender.cancel()

    app.mount("/", StaticFiles(directory=static_dir, html=True))
    return app
