from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from agent_hud.hub import Hub
from agent_hud.settings import HudSettings
from agent_hud.web.debug import router as debug_router
from agent_hud.web.socket import router as socket_router


def _not_built() -> HTMLResponse:
    return HTMLResponse(
        "<!doctype html><title>agent-hud</title><p>The canvas UI is not built. "
        "Run <code>npm run build</code> in <code>ui/</code>.</p>"
    )


def create_app(hub: Hub, settings: HudSettings, *, debug_api: bool = False) -> FastAPI:
    app = FastAPI(title="agent-hud", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.hub = hub
    app.state.settings = settings
    # Rejects DNS-rebinding requests that reach this loopback server under a foreign name.
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", settings.host])
    app.include_router(socket_router)
    if debug_api:
        app.include_router(debug_router)
    if (settings.static_dir / "index.html").is_file():
        app.mount("/", StaticFiles(directory=settings.static_dir, html=True), name="ui")
    else:
        app.add_api_route("/", _not_built, methods=["GET"], include_in_schema=False)
    return app
