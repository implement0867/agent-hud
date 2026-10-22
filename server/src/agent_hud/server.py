from typing import Annotated
from uuid import uuid4

from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_request
from mcp.types import ToolAnnotations
from pydantic import Field

from agent_hud.deps import McpHudDep
from agent_hud.hud import Hud
from agent_hud.models.actions import Action, Author, TBody
from agent_hud.models.board import Board


def build() -> FastMCP:
    mcp = FastMCP("agent-hud")

    async def write(actions: Annotated[list[TBody], Field(min_length=1)], hud: Hud = McpHudDep) -> None:
        """
        Act on the board as the agent. Actions run in order, all or nothing.
        A put replaces the card and moves its feedback to the card's history. A status tells the user what you do now.
        """
        hud.act([Action(id=uuid4().hex, author=Author.agent, body=body) for body in actions])

    async def read(
        *,
        history: Annotated[bool, Field(description="Also return the earlier versions of each card")] = False,
        hud: Hud = McpHudDep,
    ) -> Board:
        """The cards, the threads of feedback on them by ref, the values, the arrows and the chat."""
        return hud.board if history else hud.board.model_copy(update={"history": {}})

    async def listen() -> str:
        """
        The websocket URL of the user's turns. Open it with the Monitor tool, and again when the monitor ends.
        Each line is one turn: the user's actions up to their send or chat message, with the text of each part that an action names.
        """
        return str(get_http_request().url.replace(scheme="ws", path="/agent"))

    mcp.tool(write)
    mcp.tool(read, annotations=ToolAnnotations(read_only_hint=True))
    mcp.tool(listen, annotations=ToolAnnotations(read_only_hint=True))
    return mcp
