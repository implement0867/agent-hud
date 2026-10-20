from typing import Annotated

from fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from agent_hud.deps import McpStoreDep
from agent_hud.models.board import Board
from agent_hud.models.ops import Op
from agent_hud.store import BoardStore


def build() -> FastMCP:
    mcp = FastMCP("agent-hud")

    async def write(ops: Annotated[list[Op], Field(min_length=1)], store: BoardStore = McpStoreDep) -> None:
        """Change the cards on the board. Ops run in order, all or nothing.

        put {id, md}: create a card, or replace the card with that id. remove {id}: delete a card.
        """
        store.apply(ops)

    async def read(store: BoardStore = McpStoreDep) -> Board:
        """Every card on the board with its markdown."""
        return store.read()

    async def wait(store: BoardStore = McpStoreDep) -> list[str]:
        """Wait until the user presses Send on the board page. Returns the messages sent since the last wait."""
        return await store.wait_for_messages()

    mcp.tool(write)
    mcp.tool(read, annotations=ToolAnnotations(read_only_hint=True))
    mcp.tool(wait)
    return mcp
