from collections.abc import Sequence
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

from agent_hud.boards import Huds
from agent_hud.hud import Hud, Since
from agent_hud.models.actions import (
    Action,
    ActionKind,
    Author,
    Misfit,
    Put,
    TActionId,
    TAgentBody,
    TCardId,
    TQuote,
    Unlink,
)
from agent_hud.models.base import Model
from agent_hud.models.board import Board, Said
from agent_hud.schema import compact

type TActions = Annotated[list[TAgentBody], Field(min_length=1)]

BodyAdapter = TypeAdapter[TAgentBody](TAgentBody)


def agent_kinds() -> list[ActionKind]:
    """The kinds of action the agent writes: each kind but send, which is the page's."""
    return [kind for kind in ActionKind if kind is not ActionKind.send]


class Listening(Model):
    """Where the user's turns come from: a websocket URL, and a shell command that prints each turn as its lines."""

    url: str = Field(description="The websocket URL of the user's turns, for a monitor that takes a websocket")
    command: str = Field(
        description="A shell command that prints each turn as its lines, for a monitor that takes a command"
    )
    board: str = Field(description="The id of this session's board, which the URL names")
    monitors: int = Field(
        description="The monitors already open on the board: above 0, another session follows it, and both would get each turn"
    )


def board_key() -> str | None:
    """The board that the agent's request names in its X-Agent-Hud-Board header; none in memory or without the header."""
    try:
        return get_http_request().headers.get("x-agent-hud-board") or None
    except RuntimeError:
        return None


def turns_command(url: str) -> str:
    """The agent-hud-turns command on the URL, through uv in the server's project when the app runs from its source."""
    project = Path(__file__).resolve().parents[2]
    runner = (
        f"uv run --no-dev --frozen --project {quote(str(project))} " if (project / "pyproject.toml").exists() else ""
    )
    return f"{runner}agent-hud-turns {quote(url)}"


class Retired(Model):
    """A thread that went to its card's history, since the words it was on are gone."""

    card: TCardId
    quote: TQuote


class Written(Model):
    """What a write made and what it moved aside."""

    added: list[TCardId] = Field(description="The cards the write put that were not on the board")
    replaced: list[TCardId] = Field(description="The cards the write put in place of the card with that id")
    retired: list[Retired] = Field(
        description="The threads that moved to the history, since the write changed their words or removed their card"
    )
    dropped: list[TCardId] = Field(description="The arrows the write dropped, since their words or a card went")


def messages_after(chat: Sequence[Said], since: TActionId) -> tuple[Said, ...]:
    """The messages after the one with the id, if it is there; all of them when it is not."""
    found = [n for n, said in enumerate(chat) if said.id == since]
    return tuple(chat[found[-1] + 1 :] if found else chat)


def selected(board: Board, cards: list[TCardId] | None, chat: Sequence[Said]) -> Board:
    """
    The board with the given cards only, if given, with everything keyed by card or by a ref on it kept for those cards;
    and with the chat in place of its messages.
    """
    if cards is None:
        return board.model_copy(update={"messages": tuple(chat)})
    kept = set(cards)
    return board.model_copy(
        update={
            "cards": {k: v for k, v in board.cards.items() if k in kept},
            "threads": {k: v for k, v in board.threads.items() if v.card in kept},
            "arrows": {k: v for k, v in board.arrows.items() if v.card in kept or v.dst in kept},
            "messages": tuple(chat),
            "positions": {k: v for k, v in board.positions.items() if k in kept},
            "sizes": {k: v for k, v in board.sizes.items() if k in kept},
            "history": {k: v for k, v in board.history.items() if k in kept},
        }
    )


def written(before: Board, after: Board, bodies: list[TAgentBody]) -> Written:
    """What the actions made of the board and moved aside, from the board before them and after."""
    put = [body.id for body in bodies if isinstance(body, Put)]
    unlinked = {body.id for body in bodies if isinstance(body, Unlink)}
    return Written(
        added=[card_id for card_id in put if card_id not in before.cards],
        replaced=[card_id for card_id in put if card_id in before.cards],
        retired=[
            Retired(card=thread.card, quote=thread.quote)
            for card_id, versions in after.history.items()
            for version in versions[len(before.history.get(card_id, ())) :]
            for thread in version.threads.values()
        ],
        dropped=[arrow_id for arrow_id in before.arrows if arrow_id not in {*after.arrows, *unlinked}],
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
        case _, [_, *loc] if loc:
            return f"{'.'.join(loc)}: {error['msg']}"
        case _:
            return error["msg"].removeprefix("Value error, ")


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


def build(huds: Huds, token: str | None = None) -> FastMCP:
    """
    The MCP server whose tools act on the board that each request names, or on the shared board.
    With a token, the URL that listen returns carries it.
    """
    mcp = FastMCP("agent-hud")

    def hud_now() -> Hud:
        return huds.of(board_key())

    async def write(actions: Annotated[list[dict[str, Any]], Field(min_length=1)]) -> Written:
        """
        Act on the board as the agent. Actions run in order, all or nothing.
        A card is markdown; put adds it or replaces it. A comment or an arrow names a card and a quote of its words, as the card shows them.
        A thread on words that a put keeps stays with them; the rest goes to the card's history.
        Returns the cards added and replaced, the threads that went to the history, and the arrows dropped.
        """
        hud = hud_now()
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
            Field(description="Only these cards, with the threads, arrows, positions, sizes and history on them"),
        ] = None,
        since: Annotated[
            TActionId | None,
            Field(
                description="Only the cards that changed after the action with this id, such as a turn's, and the messages after it; the whole board when the board no longer has the id"
            ),
        ] = None,
    ) -> Board:
        """
        The board: the cards, the threads of comments on their words, the arrows and the chat.
        Read it once, then follow the turns; read it again when unsure, with cards or since to read less.
        """
        hud = hud_now()
        board = hud.board if history else hud.board.model_copy(update={"history": {}})
        chat: Sequence[Said] = board.messages
        match None if since is None else hud.changed_since(since):
            case Since(cards=changed, actions=ids):
                chat = [said for said in chat if said.id in ids]
                if changed is not None:
                    cards = [card_id for card_id in (board.cards if cards is None else cards) if card_id in changed]
            case None if since is not None:
                chat = messages_after(chat, since)
            case _:
                pass
        return selected(board, cards, chat)

    async def listen() -> Listening:
        """
        Where the user's turns come from: a websocket URL, and a shell command that prints each turn as its lines.
        Open the URL with the Monitor tool's websocket source, or run the command with its command source, with the description board, and again when the monitor ends.
        Each turn is one event of lines: a head with the turn's id and its number of actions, then one line per action.
        A turn with more lines than one event shows comes as several events, each with a head that counts them.
        An edit of a card on the board is a diff of its markdown.
        Also the board's id and the monitors already open on it: above 0, another session follows this board, so tell the user before you open one too.
        """
        key = board_key()
        board = huds.id_of(key)
        url = get_http_request().url.replace(scheme="ws", path="/agent").include_query_params(board=board)
        url = str(url if token is None else url.include_query_params(token=token))
        return Listening(url=url, command=turns_command(url), board=board, monitors=huds.of(key).monitors)

    tool = FunctionTool.from_function(write)
    parameters, kinds = compact(FunctionTool.from_function(listed).parameters)
    mcp.add_tool(
        tool.model_copy(update={"parameters": parameters, "description": f"{tool.description}\nActions: {kinds}."})
    )
    mcp.tool(read, annotations=ToolAnnotations(read_only_hint=True))
    mcp.tool(listen, annotations=ToolAnnotations(read_only_hint=True))
    return mcp
