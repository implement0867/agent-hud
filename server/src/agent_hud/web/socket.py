"""One websocket per open canvas tab: a snapshot on connect, then live updates both ways."""

import asyncio
import contextlib

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from agent_hud.board import Board, UserError
from agent_hud.protocol import ErrorMsg, ServerMsg, ServerType, client_messages
from agent_hud.web.deps import BoardDep, require_same_origin

router = APIRouter()


def _receive(board: Board, raw: str, queue: asyncio.Queue[ServerMsg]) -> None:
    try:
        board.handle(client_messages().validate_json(raw))
    except ValidationError as exc:
        queue.put_nowait(ErrorMsg(t=ServerType.ERROR, message=f"bad message: {exc.errors()[0]['msg']}"))
    except UserError as exc:
        queue.put_nowait(ErrorMsg(t=ServerType.ERROR, message=str(exc)))


async def _pump(ws: WebSocket, queue: asyncio.Queue[ServerMsg]) -> None:
    while True:
        msg = await queue.get()
        await ws.send_text(msg.model_dump_json())


# Async on purpose: the board is plain in-memory state owned by the event loop thread.
@router.websocket("/ws", dependencies=[Depends(require_same_origin)])
async def canvas_socket(ws: WebSocket, board: BoardDep) -> None:
    await ws.accept()
    queue: asyncio.Queue[ServerMsg] = asyncio.Queue()
    listener = queue.put_nowait
    hello = board.hello()
    board.subscribe(listener)
    pump = asyncio.create_task(_pump(ws, queue))
    try:
        await ws.send_text(hello.model_dump_json())
        while True:
            _receive(board, await ws.receive_text(), queue)
    except WebSocketDisconnect:
        pass
    finally:
        board.unsubscribe(listener)
        pump.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await pump
