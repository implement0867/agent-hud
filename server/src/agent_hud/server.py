from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from shlex import quote
from typing import Annotated, Any
from uuid import uuid4

from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_request
from fastmcp.tools import FunctionTool
from mcp.types import ToolAnnotations
from pydantic import Field, TypeAdapter, ValidationError
from pydantic_core import ErrorDetails

from agent_hud.hud import Hud
from agent_hud.models.actions import (
    Action,
    ActionKind,
    Author,
    Misfit,
    Put,
    TActionId,
    TAgentBody,
    TCardId,
    TRef,
    Unlink,
)
from agent_hud.models.base import Model
from agent_hud.models.board import Board
from agent_hud.schema import compact

type TActions = Annotated[list[TAgentBody], Field(min_length=1)]
type TParts = dict[TCardId, dict[str, str]]

BodyAdapter = TypeAdapter[TAgentBody](TAgentBody)


def agent_kinds() -> list[ActionKind]:
    """The kinds of action the agent writes: each kind but send, which is the page's."""
    return [kind for kind in ActionKind if kind is not ActionKind.send]


class Listening(Model):
    """Where the user's turns come from: a websocket URL, and a shell command that prints each turn as a line."""

    url: str = Field(description="The websocket URL of the user's turns, for a monitor that takes a websocket")
    command: str = Field(
        description="A shell command that prints each turn as a line, for a monitor that takes a command"
    )


def turns_command(url: str) -> str:
    """The agent-hud-turns command on the URL, through uv in the server's project when the app runs from its source."""
    project = Path(__file__).resolve().parents[2]
    runner = (
        f"uv run --no-dev --frozen --project {quote(str(project))} " if (project / "pyproject.toml").exists() else ""
    )
    return f"{runner}agent-hud-turns {quote(url)}"


class Written(Model):
    """What a write made and what it moved aside."""

    added: list[TCardId] = Field(description="The cards the write put that were not on the board")
    replaced: list[TCardId] = Field(description="The cards the write put in place of the card with that id")
    retired: list[TRef] = Field(
        description="The parts whose feedback moved to the history, since the write changed or removed them"
    )
    dropped: list[TCardId] = Field(
        description="The arrows the write dropped, since an end of each was on a changed part"
    )
    parts: TParts = Field(description="The text of each part of each card the write put, by card id and part number")


class Reading(Board):
    """The board as read returns it, with the parts of each card."""

    parts: TParts = Field(description="The text of each part of each card, by card id and part number")


def on_cards(ref: TRef, cards: set[TCardId]) -> bool:
    return ref.partition("/")[0] in cards


def selected(board: Board, cards: list[TCardId] | None, since: TActionId | None) -> Board:
    """
    The board with the given cards only, if given, with everything keyed by card or by a ref on it kept for those cards;
    and with the messages after the one with the id since, if it is there.
    """
    chat = board.messages
    if since is not None and (found := [n for n, said in enumerate(chat) if said.id == since]):
        chat = chat[found[-1] + 1 :]
    if cards is None:
        return board.model_copy(update={"messages": chat})
    kept = set(cards)
    return board.model_copy(
        update={
            "cards": {k: v for k, v in board.cards.items() if k in kept},
            "threads": {k: v for k, v in board.threads.items() if on_cards(k, kept)},
            "values": {k: v for k, v in board.values.items() if on_cards(k, kept)},
            "arrows": {k: v for k, v in board.arrows.items() if on_cards(v.src, kept) or on_cards(v.dst, kept)},
            "messages": chat,
            "positions": {k: v for k, v in board.positions.items() if k in kept},
            "history": {k: v for k, v in board.history.items() if k in kept},
        }
    )


def put_ids(bodies: list[TAgentBody]) -> Iterator[TCardId]:
    """The id of each card that the actions put."""
    for body in bodies:
        match body:
            case Put(id=card_id):
                yield card_id
            case _:
                pass


def unlinked(bodies: list[TAgentBody]) -> set[TCardId]:
    """The id of each arrow that the actions unlink."""
    return {body.id for body in bodies if isinstance(body, Unlink)}


def written(before: Board, after: Board, bodies: list[TAgentBody]) -> Written:
    """What the actions made of the board and moved aside, from the board before them and after."""
    put = list(put_ids(bodies))
    return Written(
        added=[card_id for card_id in put if card_id not in before.cards],
        replaced=[card_id for card_id in put if card_id in before.cards],
        retired=[
            ref
            for card_id, versions in after.history.items()
            for version in versions[len(before.history.get(card_id, ())) :]
            for ref in version.threads
        ],
        dropped=[arrow_id for arrow_id in before.arrows if arrow_id not in {*after.arrows, *unlinked(bodies)}],
        parts={card_id: after.texts_of(card_id) for card_id in put},
    )


def detail(error: ErrorDetails) -> str:
    """One validation error on an action, in a line: the field and what is wrong with it, or the kind that is not one."""
    kinds = ", ".join(agent_kinds())
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


def parse(actions: list[dict[str, Any]]) -> list[TAgentBody]:
    """
    The actions as the model of their kind takes them.
    Misfit, with the index of the action, if one does not fit its kind, or puts a card that an earlier one puts.
    """
    bodies: list[TAgentBody] = []
    puts: dict[TCardId, int] = {}
    for n, action in enumerate(actions, start=1):
        try:
            bodies.append(BodyAdapter.validate_python(action))
        except ValidationError as error:
            kind = action.get("kind")
            reasons = ", ".join(detail(found) for found in error.errors())
            raise Misfit(n, ActionKind(kind) if kind in agent_kinds() else None, reasons) from error
        match bodies[-1]:
            case Put(id=card_id) if card_id in puts:
                raise Misfit(n, ActionKind.put, f"card '{card_id}' is already put by action {puts[card_id]}")
            case Put(id=card_id):
                puts[card_id] = n
            case _:
                pass
    return bodies


def build(hud: Hud, token: str | None = None) -> FastMCP:
    """The MCP server whose tools act on the hud. With a token, the URL that listen returns carries it."""
    mcp = FastMCP("agent-hud")

    async def write(actions: Annotated[list[dict[str, Any]], Field(min_length=1)]) -> Written:
        """
        Act on the board as the agent. Actions run in order, all or nothing.
        A put replaces the card. Feedback on a part whose text is unchanged stays with it; the rest goes to the card's history.
        A ref is a card id, a part of the card such as plan/2, or an input cell such as plan/2/3.
        Returns the cards added and replaced, the parts whose feedback went to the history, the arrows dropped,
        and the parts of each card put, by number: use these numbers in refs.
        """
        before = hud.board
        try:
            bodies = parse(actions)
            now = datetime.now(UTC)
            hud.act([Action(id=uuid4().hex, author=Author.agent, body=body, at=now) for body in bodies])
        except Misfit as misfit:
            raise ValueError(misfit.in_batch()) from misfit
        return written(before, hud.board, bodies)

    def listed(actions: TActions) -> None:
        """The signature of write with the model of each kind of action, for the listed schema."""

    async def read(
        *,
        history: Annotated[bool, Field(description="Also return the earlier versions of each card")] = False,
        cards: Annotated[
            list[TCardId] | None,
            Field(description="Only these cards, with the feedback, values, arrows, positions and history on them"),
        ] = None,
        since: Annotated[
            TActionId | None, Field(description="Only the messages after the message or comment with this id")
        ] = None,
    ) -> Reading:
        """
        The board: the cards and the parts of each by number, the threads of feedback on them by ref, the values, the arrows and the chat.
        Read it once, then follow the turns; read it again when unsure, with cards or since to read less.
        """
        board = hud.board if history else hud.board.model_copy(update={"history": {}})
        board = selected(board, cards, since)
        return Reading(**dict(board), parts={card_id: board.texts_of(card_id) for card_id in board.cards})

    async def listen() -> Listening:
        """
        Where the user's turns come from: a websocket URL, and a shell command that prints each turn as a line.
        Open the URL with the Monitor tool's websocket source, or run the command with its command source, with the description board, and again when the monitor ends.
        Each line is one turn: the changes that the user made up to their send or chat message, with the text of each part that a change names.
        An edit of a card on the board is a diff of its markdown.
        """
        url = get_http_request().url.replace(scheme="ws", path="/agent")
        url = str(url if token is None else url.include_query_params(token=token))
        return Listening(url=url, command=turns_command(url))

    tool = FunctionTool.from_function(write)
    parameters, kinds = compact(FunctionTool.from_function(listed).parameters)
    mcp.add_tool(
        tool.model_copy(update={"parameters": parameters, "description": f"{tool.description}\nActions: {kinds}."})
    )
    mcp.tool(read, annotations=ToolAnnotations(read_only_hint=True))
    mcp.tool(listen, annotations=ToolAnnotations(read_only_hint=True))
    return mcp
