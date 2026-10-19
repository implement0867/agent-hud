"""Agent side over HTTP, for `--mode serve` only: drive the board from scripts and browser tests."""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Query, status
from fastapi.responses import PlainTextResponse

from agent_hud.ops import Op
from agent_hud.web.deps import BoardDep, require_debug_header

router = APIRouter(prefix="/debug", dependencies=[Depends(require_debug_header)])


# Async on purpose: the board is plain in-memory state owned by the event loop thread.
@router.post("/write", status_code=status.HTTP_204_NO_CONTENT)
async def debug_write(ops: Annotated[list[Op], Body(min_length=1)], board: BoardDep) -> None:
    board.apply(ops)


@router.get("/read")
async def debug_read(board: BoardDep, show: Annotated[list[str] | None, Query()] = None) -> PlainTextResponse:
    out = board.report()
    return PlainTextResponse(f"{out}\n\n{board.show(show)}" if show else out)
