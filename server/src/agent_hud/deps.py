from fastapi import Depends, HTTPException, WebSocket, WebSocketException, status
from fastapi.params import Depends as DependsParam
from starlette.requests import HTTPConnection


def check_same_origin(websocket: WebSocket) -> bool:
    """Whether the socket's Origin is the app's own. Websockets skip CORS, so a page of any site could open one without this check."""
    return websocket.headers.get("origin") == f"http://{websocket.headers['host']}"


def require_page_origin(websocket: WebSocket) -> None:
    """The page's socket: the browser always sends the Origin, so a request without one is not the page."""
    if not check_same_origin(websocket):
        raise WebSocketException(status.WS_1008_POLICY_VIOLATION, "the origin is not the board's")


def require_agent_origin(websocket: WebSocket) -> None:
    """The agent's socket: the monitor sends no Origin, and a page may only from the app's own."""
    if "origin" in websocket.headers and not check_same_origin(websocket):
        raise WebSocketException(status.WS_1008_POLICY_VIOLATION, "the origin is not the board's")


def make_token_dep(token: str) -> DependsParam:
    """
    A dependency that rejects a request or a socket whose token query parameter is not the app's token:
    403 for a request, and a close with a policy violation for a socket.
    """

    def require_token(connection: HTTPConnection) -> None:
        match connection.query_params.get("token") == token, connection:
            case True, _:
                pass
            case False, WebSocket():
                raise WebSocketException(status.WS_1008_POLICY_VIOLATION, "the token is missing or wrong")
            case False, _:
                raise HTTPException(status.HTTP_403_FORBIDDEN, "the token is missing or wrong")

    return Depends(require_token)


PageOriginDep = Depends(require_page_origin)
AgentOriginDep = Depends(require_agent_origin)
