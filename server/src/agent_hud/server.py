from typing import Annotated

from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_request
from mcp.types import ToolAnnotations
from pydantic import Field

from agent_hud.deps import McpStoreDep
from agent_hud.models.board import Board
from agent_hud.models.ops import TOp
from agent_hud.store import BoardStore


def build() -> FastMCP:
    mcp = FastMCP("agent-hud")

    async def write(ops: Annotated[list[TOp], Field(min_length=1)], store: BoardStore = McpStoreDep) -> None:
        """Change the cards on the board. Ops run in order, all or nothing.

        put {id, md}: create a card, or replace the card with that id. remove {id}: delete a card.
        """
        store.apply(ops)

    async def read(store: BoardStore = McpStoreDep) -> Board:
        """Every card on the board with its markdown and the user's reaction."""
        return store.read()

    async def listen() -> str:
        """The websocket URL of the user's messages and reactions. Open it with the Monitor tool, and again when the monitor ends."""
        return str(get_http_request().url.replace(scheme="ws", path="/agent"))

    mcp.tool(write)
    mcp.tool(read, annotations=ToolAnnotations(read_only_hint=True))
    mcp.tool(listen, annotations=ToolAnnotations(read_only_hint=True))
    return mcp
