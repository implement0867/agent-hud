import asyncio
import socket
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
import uvicorn

from agent_hud.settings import get_settings
from agent_hud.web import create_app


@pytest.fixture(scope="module")
def static_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """An empty directory for the UI, for the tests that do not open the page in a browser."""
    return tmp_path_factory.mktemp("static")


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def address(static_dir: Path) -> AsyncIterator[tuple[str, int]]:
    """Host and port of the app on a free port, in the module's event loop."""
    with pytest.MonkeyPatch.context() as env:
        env.setenv("AGENT_HUD_STATIC_DIR", str(static_dir))
        get_settings.cache_clear()
        app = create_app()
    get_settings.cache_clear()
    # With IPPROTO_TCP, asyncio turns off Nagle's algorithm on each connection, as for the socket uvicorn binds itself.
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
    sock.bind(("127.0.0.1", 0))
    sock.listen()
    server = uvicorn.Server(uvicorn.Config(app, log_config=None))
    task = asyncio.create_task(server.serve(sockets=[sock]))
    yield sock.getsockname()
    server.should_exit = True
    await task
