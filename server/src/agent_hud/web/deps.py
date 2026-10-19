"""Typed dependencies for the canvas routes.

The board and settings belong to the host process (the MCP server or `--mode serve`), which
hands them to `create_app`; the app keeps them on `app.state` and these getters type them.
"""

from typing import Annotated

from fastapi import Depends, Header, HTTPException, WebSocket, WebSocketException, status
from starlette.requests import HTTPConnection

from agent_hud.board import Board
from agent_hud.settings import HudSettings


def get_board(conn: HTTPConnection) -> Board:
    match conn.app.state.board:
        case Board() as board:
            return board
        case other:
            raise TypeError(f"app.state.board is {type(other).__name__}, not Board")


def get_settings(conn: HTTPConnection) -> HudSettings:
    match conn.app.state.settings:
        case HudSettings() as settings:
            return settings
        case other:
            raise TypeError(f"app.state.settings is {type(other).__name__}, not HudSettings")


BoardDep = Annotated[Board, Depends(get_board)]
SettingsDep = Annotated[HudSettings, Depends(get_settings)]


def require_same_origin(ws: WebSocket, settings: SettingsDep) -> None:
    """Refuse sockets opened by pages from other origins. Browsers always send Origin."""
    origin = ws.headers.get("origin")
    if origin is None or origin == f"http://{ws.headers.get('host')}" or origin in settings.extra_origins:
        return
    raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason=f"origin {origin} not allowed")


def require_debug_header(x_agent_hud: Annotated[str | None, Header()] = None) -> None:
    """A custom header forces a CORS preflight, which this server never answers."""
    if x_agent_hud != "1":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="missing X-Agent-Hud: 1")
