from functools import lru_cache
from typing import Annotated

from fastapi import Depends, WebSocket, WebSocketException, status
from fastmcp.dependencies import Depends as McpDepends

from agent_hud.store import BoardStore


@lru_cache(maxsize=1)
def get_store() -> BoardStore:
    return BoardStore()


def require_same_origin(websocket: WebSocket) -> None:
    """Websockets skip CORS, so any site open in the browser could read the board without this check."""
    origin = websocket.headers.get("origin")
    if origin not in (None, f"http://{websocket.headers['host']}"):
        raise WebSocketException(status.WS_1008_POLICY_VIOLATION, f"origin {origin} is not allowed")


StoreDep = Annotated[BoardStore, Depends(get_store)]
McpStoreDep = McpDepends(get_store)
SameOriginDep = Depends(require_same_origin)
