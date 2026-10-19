import asyncio
import contextlib

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from agent_hud.hub import Hub
from agent_hud.page import UserError, handle
from agent_hud.protocol import ErrorMsg, ServerMsg, ServerType, client_messages
from agent_hud.web.deps import HubDep, require_same_origin

router = APIRouter()


def _receive(hub: Hub, raw: str, queue: asyncio.Queue[ServerMsg]) -> None:
    try:
        hub.publish(handle(hub.state, client_messages().validate_json(raw)))
    except ValidationError as exc:
        queue.put_nowait(ErrorMsg(t=ServerType.ERROR, message=f"bad message: {exc.errors()[0]['msg']}"))
    except UserError as exc:
        queue.put_nowait(ErrorMsg(t=ServerType.ERROR, message=str(exc)))


async def _pump(ws: WebSocket, queue: asyncio.Queue[ServerMsg]) -> None:
    while True:
        msg = await queue.get()
        await ws.send_text(msg.model_dump_json())


# Async: the board belongs to the event loop thread.
@router.websocket("/ws", dependencies=[Depends(require_same_origin)])
async def canvas_socket(ws: WebSocket, hub: HubDep) -> None:
    await ws.accept()
    queue: asyncio.Queue[ServerMsg] = asyncio.Queue()
    listener = queue.put_nowait
    hello = hub.hello()
    hub.connect(listener)
    pump = asyncio.create_task(_pump(ws, queue))
    try:
        await ws.send_text(hello.model_dump_json())
        while True:
            _receive(hub, await ws.receive_text(), queue)
    except WebSocketDisconnect:
        pass
    finally:
        hub.disconnect(listener)
        pump.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await pump
