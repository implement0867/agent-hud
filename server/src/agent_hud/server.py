import asyncio
from collections.abc import AsyncGenerator, Sequence
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from shlex import quote
from typing import Annotated
from uuid import uuid4

from fastmcp import FastMCP
from fastmcp.resources import Resource
from fastmcp.server.dependencies import get_http_request
from fastmcp.tools import FunctionTool
from mcp.server.subscriptions import InMemorySubscriptionBus, ListenHandler, ResourcesListChanged, ResourceUpdated
from mcp.types import SubscriptionsListenRequestParams, ToolAnnotations
from pydantic import AfterValidator, Field

from agent_hud.boards import BoardSummary, TBoardName, summarize
from agent_hud.hud import ChangesSince, Hud
from agent_hud.models.actions import (
    Action,
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
from agent_hud.schema import compact_actions_schema


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


def turns_command(url: str) -> str:
    """The agent-hud-turns command on the URL, through uv in the server's project when the app runs from its source."""
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


def messages_after(chat: Sequence[Said], since: TActionId) -> tuple[Said, ...]:
    """The messages after the one with the id, if it is there; all of them when it is not."""
    found = [n for n, said in enumerate(chat) if said.id == since]
    return tuple(chat[found[-1] + 1 :] if found else chat)


def select_cards(board: Board, cards: list[TCardId] | None, chat: Sequence[Said]) -> Board:
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


def board_uri(name: TBoardName) -> str:
    return f"board://{name}"


def build_mcp_server(boards: dict[TBoardName, Hud], directory: Path, token: str | None = None) -> FastMCP:
    """
    The MCP server whose tools create, list and delete the boards and act on the board that each call names.
    Each board is the resource board://<name>: a subscriber gets an update at each change of the board, and a listener
    on the list gets a change at each board created or deleted. A new board keeps its state in <directory>/<name>.db.
    With a token, the URL that listen returns carries it.
    """
    bus = InMemorySubscriptionBus()
    watchers: dict[TBoardName, asyncio.Task[None]] = {}

    async def publish_updates(name: TBoardName, hud: Hud) -> None:
        """Publish an update of the board's resource at each change of the board or of its agents."""
        async for _ in hud.snapshots():
            await bus.publish(ResourceUpdated(uri=board_uri(name)))

    def add_resource(name: TBoardName, hud: Hud) -> None:
        """Serve the board as its resource."""

        def board_json() -> str:
            return hud.board.model_dump_json()

        mcp.add_resource(
            Resource.from_function(
                board_json,
                uri=board_uri(name),
                name=name,
                description=f"The board {name}: its cards, threads, arrows, chat and history, as JSON",
                mime_type="application/json",
            )
        )

    @asynccontextmanager
    async def lifespan(server: FastMCP) -> AsyncGenerator[None]:
        """Publish the changes of each board while the server runs."""
        for name, hud in boards.items():
            watchers[name] = asyncio.create_task(publish_updates(name, hud))
        try:
            yield
        finally:
            for watcher in watchers.values():
                watcher.cancel()

    mcp = FastMCP("agent-hud", lifespan=lifespan)
    # FastMCP serves no subscriptions/listen of its own, and has no public way to add a request handler.
    mcp._mcp_server.add_request_handler(  # pyright: ignore[reportPrivateUsage]
        "subscriptions/listen", SubscriptionsListenRequestParams, ListenHandler(bus)
    )

    def board_named(name: TBoardName) -> Hud:
        """The hud of the board. ValueError when no board has the name."""
        if name not in boards:
            raise ValueError(f"no board '{name}': the boards are {', '.join(boards) or 'none'}; create_board makes one")
        return boards[name]

    async def create_board(name: TBoardName) -> BoardSummary:
        """Create an empty board with the name. ValueError when a board has the name."""
        if name in boards:
            raise ValueError(f"a board '{name}' exists")
        boards[name] = Hud(directory / f"{name}.db")
        add_resource(name, boards[name])
        watchers[name] = asyncio.create_task(publish_updates(name, boards[name]))
        await bus.publish(ResourcesListChanged())
        return summarize(name, boards[name])

    async def list_boards() -> list[BoardSummary]:
        """Each board with its number of cards and whether an agent follows it."""
        return [summarize(name, hud) for name, hud in sorted(boards.items())]

    async def delete_board(name: TBoardName) -> None:
        """
        Delete the board and its state file, for good.
        ValueError when no board has the name, or when a monitor is open on it.
        """
        hud = board_named(name)
        if hud.monitors:
            raise ValueError(f"the board '{name}' has {hud.monitors} open monitors: stop them first")
        hud.close()
        (directory / f"{name}.db").unlink(missing_ok=True)
        del boards[name]
        watchers.pop(name).cancel()
        mcp.local_provider.remove_resource(board_uri(name))
        await bus.publish(ResourcesListChanged())

    async def write(name: TBoardName, actions: TActions) -> WriteResult:
        """
        Act on the board as the agent. Actions run in order, all or nothing.
        A card is markdown; put adds it or replaces it. A comment or an arrow names a card and a quote of its words, as the card shows them.
        A thread on words that a put keeps stays with them; the rest goes to the card's history.
        Returns the cards added and replaced, the threads that went to the history, and the arrows dropped.
        """
        hud = board_named(name)
        before = hud.board
        now = datetime.now(UTC)
        try:
            hud.act([Action(id=uuid4().hex, author=Author.agent, body=body, at=now) for body in actions])
        except Misfit as misfit:
            raise ValueError(misfit.in_batch()) from misfit
        return summarize_write(before, hud.board, actions)

    async def read(
        name: TBoardName,
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
        hud = board_named(name)
        board = hud.board if history else hud.board.model_copy(update={"history": {}})
        chat: Sequence[Said] = board.messages
        match None if since is None else hud.changed_since(since):
            case ChangesSince(cards=changed, actions=ids):
                chat = [said for said in chat if said.id in ids]
                if changed is not None:
                    cards = [card_id for card_id in (board.cards if cards is None else cards) if card_id in changed]
            case None if since is not None:
                chat = messages_after(chat, since)
            case _:
                pass
        return select_cards(board, cards, chat)

    async def listen(name: TBoardName) -> Listening:
        """
        Where the user's turns on the board come from: a websocket URL, and a shell command that prints each turn as its lines.
        Open the URL with the Monitor tool's websocket source, or run the command with its command source, with the description board, and again when the monitor ends.
        Each turn is one event of lines: a head with the turn's id and its number of actions, then one line per action.
        A turn with more lines than one event shows comes as several events, each with a head that counts them.
        An edit of a card on the board is a diff of its markdown.
        Also the monitors already open on the board: above 0, another session follows this board, so tell the user before you open one too.
        """
        hud = board_named(name)
        url = get_http_request().url.replace(scheme="ws", path="/agent").include_query_params(board=name)
        url = str(url if token is None else url.include_query_params(token=token))
        return Listening(url=url, command=turns_command(url), board=name, monitors=hud.monitors)

    tool = FunctionTool.from_function(write)
    parameters, kinds = compact_actions_schema(tool.parameters)
    mcp.add_tool(
        tool.model_copy(update={"parameters": parameters, "description": f"{tool.description}\nActions: {kinds}."})
    )
    mcp.tool(create_board)
    mcp.tool(list_boards, annotations=ToolAnnotations(read_only_hint=True))
    mcp.tool(delete_board, annotations=ToolAnnotations(destructive_hint=True))
    mcp.tool(read, annotations=ToolAnnotations(read_only_hint=True))
    mcp.tool(listen, annotations=ToolAnnotations(read_only_hint=True))
    for name, hud in boards.items():
        add_resource(name, hud)
    return mcp
