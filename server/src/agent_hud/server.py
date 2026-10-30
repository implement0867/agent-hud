from collections import defaultdict
from collections.abc import Sequence
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from shlex import quote
from typing import Annotated
from uuid import uuid4

from fastmcp import FastMCP
from fastmcp.dependencies import CallArgument, Depends
from fastmcp.exceptions import ToolError
from fastmcp.resources import Resource
from fastmcp.server.dependencies import get_http_request
from fastmcp.tools import FunctionTool
from mcp.server.subscriptions import InMemorySubscriptionBus, ListenHandler, ResourcesListChanged, ResourceUpdated
from mcp.types import SubscriptionsListenRequestParams, ToolAnnotations
from pydantic import AfterValidator, Field
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from agent_hud.boards import BoardSummary, TBoardName
from agent_hud.models.actions import (
    Action,
    Author,
    Misfit,
    Put,
    TAgentBody,
    TCardId,
    TQuote,
    Unlink,
)
from agent_hud.models.base import Model
from agent_hud.models.board import Board, Message
from agent_hud.operations import apply_agent_actions, list_board_summaries
from agent_hud.presence import Presence
from agent_hud.queries.boards import (
    add_board,
    check_board_exists,
    list_board_names,
    load_board,
    remove_board,
)
from agent_hud.queries.cursors import load_cursor, save_cursor
from agent_hud.schema import compact_actions_schema
from agent_hud.settings import Settings


def check_each_card_put_once(bodies: list[TAgentBody]) -> list[TAgentBody]:
    """The actions as they are. ValueError when one puts a card that an earlier one puts."""
    puts: dict[TCardId, int] = {}
    for n, body in enumerate(bodies, start=1):
        match body:
            case Put(id=card_id) if card_id in puts:
                raise ValueError(f"action {n} (put): card '{card_id}' is already put by action {puts[card_id]}")
            case Put(id=card_id):
                puts[card_id] = n
            case _:
                pass
    return bodies


type TActions = Annotated[list[TAgentBody], Field(min_length=1), AfterValidator(check_each_card_put_once)]


class Listening(Model):
    """Where the user's turns come from: a websocket URL, and a shell command that prints each turn as its lines."""

    url: str = Field(description="The websocket URL of the user's turns, for a monitor that takes a websocket")
    command: str = Field(
        description="A shell command that prints each turn as its lines, for a monitor that takes a command"
    )
    board: TBoardName = Field(description="The name of the board, which the URL names")
    monitors: int = Field(
        description="The monitors already open on the board: above 0, another session follows it, and both would get each turn"
    )


def make_turns_command(url: str) -> str:
    """Make the agent-hud-turns command on the URL, through uv in the server's project when the app runs from its source."""
    project = Path(__file__).resolve().parents[2]
    runner = (
        f"uv run --no-dev --frozen --project {quote(str(project))} " if (project / "pyproject.toml").exists() else ""
    )
    return f"{runner}agent-hud-turns {quote(url)}"


class RetiredThread(Model):
    """A thread that went to its card's history, since the words it was on are gone."""

    card: TCardId
    quote: TQuote


class WriteResult(Model):
    """What a write made and what it moved aside."""

    added: list[TCardId] = Field(description="The cards the write put that were not on the board")
    replaced: list[TCardId] = Field(description="The cards the write put in place of the card with that id")
    retired: list[RetiredThread] = Field(
        description="The threads that moved to the history, since the write changed their words or removed their card"
    )
    dropped: list[TCardId] = Field(description="The arrows the write dropped, since their words or a card went")


def select_cards(board: Board, cards: list[TCardId] | None, chat: Sequence[Message]) -> Board:
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


def summarize_write(before: Board, after: Board, bodies: list[TAgentBody]) -> WriteResult:
    """What the actions made of the board and moved aside, from the board before them and after."""
    put = [body.id for body in bodies if isinstance(body, Put)]
    unlinked = {body.id for body in bodies if isinstance(body, Unlink)}
    return WriteResult(
        added=[card_id for card_id in put if card_id not in before.cards],
        replaced=[card_id for card_id in put if card_id in before.cards],
        retired=[
            RetiredThread(card=thread.card, quote=thread.quote)
            for card_id, versions in after.history.items()
            for version in versions[len(before.history.get(card_id, ())) :]
            for thread in version.threads.values()
        ],
        dropped=[arrow_id for arrow_id in before.arrows if arrow_id not in {*after.arrows, *unlinked}],
    )


def make_board_uri(name: TBoardName) -> str:
    return f"board://{name}"


def build_mcp_server(
    settings: Settings, engine: Engine, presences: defaultdict[TBoardName, Presence], bus: InMemorySubscriptionBus
) -> FastMCP:
    """
    The MCP server whose tools create, list and delete the boards in the database, and act on the board that each call
    names; presences holds the live presence of each board. Each board is the resource board://<name>, and bus carries
    an update of it at each write, and a change of the list at each create and delete.
    """
    mcp = FastMCP("agent-hud")
    # FastMCP serves no subscriptions/listen of its own, and has no public way to add a request handler.
    mcp._mcp_server.add_request_handler(  # pyright: ignore[reportPrivateUsage]
        "subscriptions/listen", SubscriptionsListenRequestParams, ListenHandler(bus)
    )

    call_session = Depends(partial(Session, engine))

    def add_resource(name: TBoardName) -> None:
        def dump_board() -> str:
            with Session(engine) as session:
                return load_board(session, name).model_dump_json()

        mcp.add_resource(
            Resource.from_function(
                dump_board,
                uri=make_board_uri(name),
                name=name,
                description=f"The board {name} as JSON",
                mime_type="application/json",
            )
        )

    def find_presence(name: TBoardName, session: Session = call_session) -> Presence:
        """The presence of the board with the name. ToolError when no board has the name, since FastMCP hides any other error from a dependency."""
        if not check_board_exists(session, name):
            boards = ", ".join(list_board_names(session)) or "none"
            raise ToolError(f"no board '{name}': the boards are {boards}; create_board makes one")
        return presences[name]

    board_presence = Depends(find_presence, name=CallArgument())

    async def create_board(name: TBoardName, session: Session = call_session) -> BoardSummary:
        """Create an empty board with the name. ValueError when a board has the name."""
        add_board(session, name)
        session.commit()
        add_resource(name)
        await bus.publish(ResourcesListChanged())
        return BoardSummary(name=name, card_count=0, agent=presences[name].agent_state)

    async def list_boards(session: Session = call_session) -> list[BoardSummary]:
        """Each board with its number of cards and whether an agent follows it."""
        return list_board_summaries(session, presences)

    async def delete_board(
        name: TBoardName, presence: Presence = board_presence, session: Session = call_session
    ) -> None:
        """
        Delete the board.
        ValueError when no board has the name, or when a monitor is open on it.
        """
        if presence.monitors:
            raise ValueError(f"the board '{name}' has {len(presence.monitors)} open monitors: stop them first")
        remove_board(session, name)
        session.commit()
        del presences[name]
        mcp.local_provider.remove_resource(make_board_uri(name))
        await bus.publish(ResourcesListChanged())

    async def write_board(
        name: TBoardName, actions: TActions, presence: Presence = board_presence, session: Session = call_session
    ) -> WriteResult:
        """
        Act on the board as the agent. Actions run in order, all or nothing.
        A card is markdown; put adds it or replaces it. A comment or an arrow names a card and a quote of its words, as the card shows them.
        A thread on words that a put keeps stays with them; the rest goes to the card's history.
        Returns the cards added and replaced, the threads that went to the history, and the arrows dropped.
        """
        now = datetime.now(UTC)
        try:
            change = apply_agent_actions(
                session, name, [Action(id=uuid4().hex, author=Author.agent, body=body, at=now) for body in actions]
            )
        except Misfit as misfit:
            raise ValueError(misfit.describe_in_batch()) from misfit
        presence.note_agent_wrote()
        presence.notify_change()
        await bus.publish(ResourceUpdated(uri=make_board_uri(name)))
        return summarize_write(change.before, change.after, actions)

    async def read_board(
        name: TBoardName,
        presence: Presence = board_presence,
        session: Session = call_session,
        *,
        history: Annotated[bool, Field(description="Also return the earlier versions of each card")] = False,
        cards: Annotated[
            list[TCardId] | None,
            Field(description="Only these cards, with the threads, arrows, positions, sizes and history on them"),
        ] = None,
    ) -> Board:
        """
        The board: the cards, the threads of comments on their words, the arrows and the chat.
        Read it once, then follow the turns and read the changes; read it again when unsure, with cards to read less.
        """
        whole = load_board(session, name)
        board = whole if history else whole.model_copy(update={"history": {}})
        read_cards = frozenset(board.cards if cards is None else cards)
        save_cursor(session, name, load_cursor(session, name).mark_read(read_cards, len(board.messages)))
        session.commit()
        return select_cards(board, cards, board.messages)

    async def read_changes(
        name: TBoardName, presence: Presence = board_presence, session: Session = call_session
    ) -> Board:
        """
        The cards that changed since you last read them, with what is on them, and the messages since you last read
        the board. Each read moves past what it returns; read the whole board to start again.
        """
        board = load_board(session, name).model_copy(update={"history": {}})
        cursor = load_cursor(session, name)
        changed = [card_id for card_id in board.cards if card_id in cursor.unread_cards]
        save_cursor(session, name, cursor.mark_read(cursor.unread_cards, len(board.messages)))
        session.commit()
        return select_cards(board, changed, board.messages[cursor.read_message_count :])

    async def listen_board(name: TBoardName, presence: Presence = board_presence) -> Listening:
        """
        Where the user's turns on the board come from: a websocket URL, and a shell command that prints each turn as its lines.
        Open the URL with the Monitor tool's websocket source, or run the command with its command source, with the description board, and again when the monitor ends.
        Each turn is one event of lines: a head with the turn's id and its number of actions, then one line per action.
        A turn with more lines than one event shows comes as several events, each with a head that counts them.
        An edit of a card on the board is a diff of its markdown.
        Also the monitors already open on the board: above 0, another session follows this board, so tell the user before you open one too.
        """
        request_url = get_http_request().url.replace(scheme="ws", path="/agent")
        url = str(request_url.include_query_params(board=name, token=settings.socket_token))
        return Listening(url=url, command=make_turns_command(url), board=name, monitors=len(presence.monitors))

    tool = FunctionTool.from_function(write_board)
    parameters, kinds = compact_actions_schema(tool.parameters)
    mcp.add_tool(
        tool.model_copy(update={"parameters": parameters, "description": f"{tool.description}\nActions: {kinds}."})
    )
    mcp.tool(create_board)
    mcp.tool(list_boards, annotations=ToolAnnotations(read_only_hint=True))
    mcp.tool(delete_board, annotations=ToolAnnotations(destructive_hint=True))
    mcp.tool(read_board, annotations=ToolAnnotations(read_only_hint=True))
    mcp.tool(read_changes, annotations=ToolAnnotations(read_only_hint=True))
    mcp.tool(listen_board, annotations=ToolAnnotations(read_only_hint=True))
    with Session(engine) as session:
        for name in list_board_names(session):
            add_resource(name)
    return mcp
