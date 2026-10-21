import asyncio
from typing import assert_never

from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from agent_hud.deps import SameOriginDep, StoreDep
from agent_hud.models.events import BoardChanged, EventKind, MessageReceived, MessageSent, PageEvent, ReactionSet
from agent_hud.server import build
from agent_hud.settings import get_settings
from agent_hud.store import BoardStore


async def send_boards(websocket: WebSocket, store: BoardStore) -> None:
    async for board in store.watch():
        await websocket.send_text(BoardChanged(kind=EventKind.board_changed, board=board).model_dump_json())


async def send_messages(websocket: WebSocket, messages: asyncio.Queue[str]) -> None:
    while True:
        message = await messages.get()
        await websocket.send_text(MessageSent(kind=EventKind.message_sent, message=message).model_dump_json())


def create_app() -> FastAPI:
    """MCP for the agent at /mcp/, the board websocket at /ws, and the built UI at /."""
    mcp_app = build().http_app(path="/")
    app = FastAPI(lifespan=mcp_app.lifespan)
    # A DNS rebinding page sends its own name as Host, which passes the origin check.
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])

    @app.websocket("/ws", dependencies=[SameOriginDep])
    async def board_updates(websocket: WebSocket, store: StoreDep) -> None:
        """Send the board on connect and after each change, and take the page's messages and reactions, until it disconnects."""
        await websocket.accept()
        async with asyncio.TaskGroup() as tg:
            sender = tg.create_task(send_boards(websocket, store))
            async for text in websocket.iter_text():
                match event := PageEvent.model_validate_json(text).root:
                    case MessageSent(message=message):
                        store.add_message(message)
                        await websocket.send_text(MessageReceived(kind=EventKind.message_received).model_dump_json())
                    case ReactionSet(id=card_id, reaction=reaction):
                        store.react(card_id, reaction)
                    case _:
                        assert_never(event)
            sender.cancel()

    @app.websocket("/agent", dependencies=[SameOriginDep])
    async def agent_messages(websocket: WebSocket, store: StoreDep) -> None:
        """Send each message from the page to this agent's monitor, until it disconnects."""
        # Listen before accept: the client's handshake ends only after accept, so it misses no message.
        with store.listen() as messages:
            await websocket.accept()
            async with asyncio.TaskGroup() as tg:
                sender = tg.create_task(send_messages(websocket, messages))
                # The monitor sends nothing, so this returns when it disconnects.
                await websocket.receive()
                sender.cancel()

    app.mount("/mcp", mcp_app)
    app.mount("/", StaticFiles(directory=get_settings().static_dir, html=True))
    return app
