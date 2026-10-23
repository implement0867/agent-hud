from fastapi import Depends, WebSocket, WebSocketException, status
from fastapi.params import Depends as DependsParam


def same_origin(websocket: WebSocket) -> bool:
    """Whether the socket's Origin is the app's own. Websockets skip CORS, so a page of any site could open one without this check."""
    return websocket.headers.get("origin") == f"http://{websocket.headers['host']}"


def require_page_origin(websocket: WebSocket) -> None:
    """The page's socket: the browser always sends the Origin, so a request without one is not the page."""
    if not same_origin(websocket):
        raise WebSocketException(status.WS_1008_POLICY_VIOLATION, "the origin is not the board's")


def require_agent_origin(websocket: WebSocket) -> None:
    """The agent's socket: the monitor sends no Origin, and a page may only from the app's own."""
    if "origin" in websocket.headers and not same_origin(websocket):
        raise WebSocketException(status.WS_1008_POLICY_VIOLATION, "the origin is not the board's")


def token_dep(token: str) -> DependsParam:
    """A dependency that rejects a socket whose token query parameter is not the app's token."""

    def require_token(websocket: WebSocket) -> None:
        if websocket.query_params.get("token") != token:
            raise WebSocketException(status.WS_1008_POLICY_VIOLATION, "the token is missing or wrong")

    return Depends(require_token)


PageOriginDep = Depends(require_page_origin)
AgentOriginDep = Depends(require_agent_origin)
