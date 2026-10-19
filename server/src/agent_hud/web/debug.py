from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from fastapi.responses import PlainTextResponse

from agent_hud.agent import OpError, apply
from agent_hud.ops import Op
from agent_hud.report import report, show_cards
from agent_hud.state import Delta
from agent_hud.web.deps import HubDep, require_debug_header

router = APIRouter(prefix="/debug", dependencies=[Depends(require_debug_header)])


# Async: the board belongs to the event loop thread.
@router.post("/write", status_code=status.HTTP_204_NO_CONTENT)
async def debug_write(ops: Annotated[list[Op], Body(min_length=1)], hub: HubDep) -> None:
    try:
        hub.state, delta = apply(hub.state, ops)
    except OpError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from None
    hub.publish(delta)


@router.get("/read")
async def debug_read(hub: HubDep, show: Annotated[list[str] | None, Query()] = None) -> PlainTextResponse:
    out = report(hub.state)
    hub.publish(Delta())
    return PlainTextResponse(f"{out}\n\n{show_cards(hub.state, show)}" if show else out)
