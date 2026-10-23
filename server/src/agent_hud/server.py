from collections.abc import Iterator
from typing import Annotated, Any
from uuid import uuid4

from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_request
from fastmcp.tools import FunctionTool
from mcp.types import ToolAnnotations
from pydantic import Field, TypeAdapter, ValidationError
from pydantic_core import ErrorDetails

from agent_hud.hud import Hud
from agent_hud.models.actions import Action, ActionKind, Author, Misfit, Put, TBody, TCardId
from agent_hud.models.base import Model
from agent_hud.models.board import Board
from agent_hud.schema import compact

type TActions = Annotated[list[TBody], Field(min_length=1)]
type TParts = dict[TCardId, dict[str, str]]

BodyAdapter = TypeAdapter[TBody](TBody)


class Written(Model):
    """What a write made: the parts of each card it put."""

    parts: TParts = Field(description="The text of each part of each card the write put, by card id and part number")


class Reading(Board):
    """The board as read returns it, with the parts of each card."""

    parts: TParts = Field(description="The text of each part of each card, by card id and part number")


def put_ids(bodies: list[TBody]) -> Iterator[TCardId]:
    """The id of each card that the actions put."""
    for body in bodies:
        match body:
            case Put(id=card_id):
                yield card_id
            case _:
                pass


def parts_put(board: Board, bodies: list[TBody]) -> TParts:
    """The parts of each card that the actions put, as the board has them after the actions."""
    return {card_id: board.texts_of(card_id) for card_id in put_ids(bodies)}


def detail(error: ErrorDetails) -> str:
    """One validation error on an action, in a line: the field and what is wrong with it, or the kind that is not one."""
    kinds = ", ".join(ActionKind)
    match error["type"], [str(part) for part in error["loc"]]:
        case "union_tag_invalid", _:
            return f"kind '{error.get('ctx', {}).get('tag')}' is not one of {kinds}"
        case "union_tag_not_found", _:
            return f"kind is missing: one of {kinds}"
        case "extra_forbidden", [kind, *loc]:
            return f"{'.'.join(loc)}: not a field of {kind}"
        case _, [_, *loc]:
            return f"{'.'.join(loc)}: {error['msg']}"
        case _:
            return error["msg"]


def parse(actions: list[dict[str, Any]]) -> list[TBody]:
    """The actions as the model of their kind takes them. Misfit, with the index of the action, if one does not fit its kind."""
    bodies: list[TBody] = []
    for n, action in enumerate(actions, start=1):
        try:
            bodies.append(BodyAdapter.validate_python(action))
        except ValidationError as error:
            kind = action.get("kind")
            reasons = ", ".join(detail(found) for found in error.errors())
            raise Misfit(n, ActionKind(kind) if kind in list(ActionKind) else None, reasons) from error
    return bodies


def build(hud: Hud) -> FastMCP:
    """The MCP server whose tools act on the hud."""
    mcp = FastMCP("agent-hud")

    async def write(actions: Annotated[list[dict[str, Any]], Field(min_length=1)]) -> Written:
        """
        Act on the board as the agent. Actions run in order, all or nothing.
        A put replaces the card and moves its feedback to the card's history.
        A ref is a card id, a part of the card such as plan/2, or an input cell such as plan/2/3.
        Returns the parts of each card put, by number: use these numbers in refs.
        """
        try:
            bodies = parse(actions)
            hud.act([Action(id=uuid4().hex, author=Author.agent, body=body) for body in bodies])
        except Misfit as misfit:
            raise ValueError(misfit.in_batch()) from misfit
        return Written(parts=parts_put(hud.board, bodies))

    def listed(actions: TActions) -> None:
        """The signature of write with the model of each kind of action, for the listed schema."""

    async def read(
        *,
        history: Annotated[bool, Field(description="Also return the earlier versions of each card")] = False,
    ) -> Reading:
        """The whole board: the cards and the parts of each by number, the threads of feedback on them by ref, the values, the arrows and the chat. Read it once, then follow the turns; read it again when unsure."""
        board = hud.board if history else hud.board.model_copy(update={"history": {}})
        return Reading(**dict(board), parts={card_id: board.texts_of(card_id) for card_id in board.cards})

    async def listen() -> str:
        """
        The websocket URL of the user's turns. Open it with the Monitor tool, and again when the monitor ends.
        Each line is one turn: the changes that the user made up to their send or chat message, with the text of each part that a change names.
        An edit of a card on the board is a diff of its markdown.
        """
        return str(get_http_request().url.replace(scheme="ws", path="/agent"))

    tool = FunctionTool.from_function(write)
    parameters, kinds = compact(FunctionTool.from_function(listed).parameters)
    mcp.add_tool(
        tool.model_copy(update={"parameters": parameters, "description": f"{tool.description}\nActions: {kinds}."})
    )
    mcp.tool(read, annotations=ToolAnnotations(read_only_hint=True))
    mcp.tool(listen, annotations=ToolAnnotations(read_only_hint=True))
    return mcp
