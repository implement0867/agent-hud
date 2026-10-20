import asyncio

import uvicorn

from agent_hud.changes import Changes
from agent_hud.models.board import Board
from agent_hud.server import build
from agent_hud.settings import Settings, get_settings
from agent_hud.web import create_app


async def serve(settings: Settings) -> None:
    """MCP on stdio and the board page over HTTP, both on one board, until stdin closes."""
    board = Board()
    changes = Changes()
    # stdout carries MCP, and uvicorn's default log config writes access lines there.
    config = uvicorn.Config(create_app(board, changes, settings.static_dir), port=settings.port, log_config=None)
    page = uvicorn.Server(config)
    async with asyncio.TaskGroup() as tg:
        tg.create_task(page.serve())
        await build(board, changes).run_async(show_banner=False)
        page.should_exit = True


def main() -> None:
    asyncio.run(serve(get_settings()))
