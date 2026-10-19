from typing import Annotated

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from agent_hud.board import Board, Op, OpError


class Canvas:
    def __init__(self) -> None:
        self.board: Board = Board()

    # Async tools run on the event loop, one at a time, so two writes cannot interleave.
    async def write(self, ops: Annotated[list[Op], Field(min_length=1)]) -> str:
        """Change the cards on the canvas. Ops run in order, all or nothing.

        put {id, md}: create a card, or replace the card with that id. remove {id}: delete a card.
        """
        try:
            self.board = self.board.apply(ops)
        except OpError as exc:
            raise ToolError(str(exc)) from None
        return "ok"

    async def read(self) -> str:
        """Every card on the canvas with its markdown."""
        return self.board.render()


def build() -> FastMCP:
    canvas = Canvas()
    mcp = FastMCP("agent-hud")
    mcp.tool(canvas.write, output_schema=None)
    mcp.tool(canvas.read, output_schema=None, annotations=ToolAnnotations(read_only_hint=True))
    return mcp


def main() -> None:
    build().run(show_banner=False)
