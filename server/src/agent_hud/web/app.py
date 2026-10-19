"""Application factory for the canvas: static UI, websocket, and the optional debug API."""

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from agent_hud.board import Board, OpError
from agent_hud.settings import HudSettings
from agent_hud.web.debug import router as debug_router
from agent_hud.web.socket import router as socket_router


def _op_error(_: Request, exc: Exception) -> JSONResponse:
    match exc:
        case OpError(status_code=code):
            return JSONResponse(status_code=code, content={"detail": str(exc)})
        case _:
            raise exc


def _not_built() -> HTMLResponse:
    return HTMLResponse(
        "<!doctype html><title>agent-hud</title><p>The canvas UI is not built. "
        "Run <code>npm run build</code> in <code>ui/</code>.</p>"
    )


def create_app(
    board: Board, settings: HudSettings, *, debug_api: bool = False, allowed_hosts: list[str] | None = None
) -> FastAPI:
    app = FastAPI(title="agent-hud", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.board = board
    app.state.settings = settings
    # Rejects DNS-rebinding requests that reach this loopback server under a foreign name.
    hosts = allowed_hosts or ["127.0.0.1", "localhost", settings.host]
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=hosts)
    app.add_exception_handler(OpError, _op_error)
    app.include_router(socket_router)
    if debug_api:
        app.include_router(debug_router)
    if (settings.static_dir / "index.html").is_file():
        app.mount("/", StaticFiles(directory=settings.static_dir, html=True), name="ui")
    else:
        app.add_api_route("/", _not_built, methods=["GET"], include_in_schema=False)
    return app
