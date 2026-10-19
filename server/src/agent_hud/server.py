from typing import Annotated

from fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from agent_hud.models.board import Board
from agent_hud.models.ops import Op


def build(board: Board) -> FastMCP:
    mcp = FastMCP("agent-hud")

    async def write(ops: Annotated[list[Op], Field(min_length=1)]) -> None:
        """Change the cards on the board. Ops run in order, all or nothing.

        put {id, md}: create a card, or replace the card with that id. remove {id}: delete a card.
        """
        board.apply(ops)

    async def read() -> Board:
        """Every card on the board with its markdown."""
        return board

    mcp.tool(write)
    mcp.tool(read, annotations=ToolAnnotations(read_only_hint=True))
    return mcp


def main() -> None:
    build(Board()).run(show_banner=False)
