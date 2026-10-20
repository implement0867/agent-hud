from fastapi import Depends, WebSocket, WebSocketException, status


def require_same_origin(websocket: WebSocket) -> None:
    """Websockets skip CORS, so any site open in the browser could read the board without this check."""
    origin = websocket.headers.get("origin")
    if origin not in (None, f"http://{websocket.headers['host']}"):
        raise WebSocketException(status.WS_1008_POLICY_VIOLATION, f"origin {origin} is not allowed")


SameOriginDep = Depends(require_same_origin)
