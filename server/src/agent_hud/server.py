import asyncio
from typing import Annotated

import uvicorn
from fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from agent_hud.changes import Changes
from agent_hud.models.board import Board
from agent_hud.models.ops import Op
from agent_hud.settings import Settings
from agent_hud.web import create_app


def build(board: Board, changes: Changes) -> FastMCP:
    mcp = FastMCP("agent-hud")

    async def write(ops: Annotated[list[Op], Field(min_length=1)]) -> None:
        """Change the cards on the board. Ops run in order, all or nothing.

        put {id, md}: create a card, or replace the card with that id. remove {id}: delete a card.
        """
        board.apply(ops)
        changes.notify()

    async def read() -> Board:
        """Every card on the board with its markdown."""
        return board

    mcp.tool(write)
    mcp.tool(read, annotations=ToolAnnotations(read_only_hint=True))
    return mcp


async def serve(settings: Settings) -> None:
    """MCP on stdio and the board page on http://127.0.0.1:{port}, until stdin closes."""
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
    asyncio.run(serve(Settings()))
