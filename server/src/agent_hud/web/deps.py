from typing import Annotated

from fastapi import Depends, Header, HTTPException, WebSocket, WebSocketException, status
from starlette.requests import HTTPConnection

from agent_hud.hub import Hub
from agent_hud.settings import HudSettings


def get_hub(conn: HTTPConnection) -> Hub:
    match conn.app.state.hub:
        case Hub() as hub:
            return hub
        case other:
            raise TypeError(f"app.state.hub is {type(other).__name__}, not Hub")


def get_settings(conn: HTTPConnection) -> HudSettings:
    match conn.app.state.settings:
        case HudSettings() as settings:
            return settings
        case other:
            raise TypeError(f"app.state.settings is {type(other).__name__}, not HudSettings")


HubDep = Annotated[Hub, Depends(get_hub)]
SettingsDep = Annotated[HudSettings, Depends(get_settings)]


def require_same_origin(ws: WebSocket, settings: SettingsDep) -> None:
    origin = ws.headers.get("origin")
    if origin is None or origin == f"http://{ws.headers.get('host')}" or origin in settings.extra_origins:
        return
    raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason=f"origin {origin} not allowed")


def require_debug_header(x_agent_hud: Annotated[str | None, Header()] = None) -> None:
    # A custom header forces a CORS preflight, which this server never answers.
    if x_agent_hud != "1":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="missing X-Agent-Hud: 1")
