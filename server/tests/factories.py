from typing import Any

from fastmcp import Client
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from agent_hud.exchange import Exchange, act_on_board
from agent_hud.models.actions import (
    Action,
    ActionKind,
    Clear,
    Comment,
    Link,
    Move,
    Place,
    Put,
    Remove,
    Resize,
    Restore,
    Say,
    Send,
    TBody,
    Unlink,
)
from agent_hud.models.board import Board
from agent_hud.models.state import BoardState
from agent_hud.queries.boards import add_board, load_board_state

# The board that the tests' tools and sockets name.
BOARD = "test"


class BoardExchange(Exchange):
    """An exchange with its database, so that a test acts on the board and reads it as the app does."""

    def __init__(self, engine: Engine, name: str) -> None:
        super().__init__(name)
        self.engine = engine

    @property
    def state(self) -> BoardState:
        with Session(self.engine) as session:
            return load_board_state(session, self.name)

    @property
    def board(self) -> Board:
        return self.state.board

    def act(self, actions: list[Action]) -> None:
        """Act on the board as the page and the tools do."""
        with Session(self.engine) as session:
            act_on_board(session, self, actions)


def create_exchange(engine: Engine, name: str = BOARD) -> BoardExchange:
    """Add a board with the name to the database, and make its exchange."""
    with Session(engine) as session:
        add_board(session, name)
        session.commit()
    return BoardExchange(engine, name)


def put(card_id: str, md: str, version: int | None = None) -> Put:
    return Put(kind=ActionKind.put, id=card_id, md=md, version=version)


def remove(card_id: str) -> Remove:
    return Remove(kind=ActionKind.remove, id=card_id)


def restore(card_id: str) -> Restore:
    return Restore(kind=ActionKind.restore, id=card_id)


def comment(card_id: str, text: str, quote: str = "", occurrence: int | None = None) -> Comment:
    return Comment(kind=ActionKind.comment, card=card_id, quote=quote, occurrence=occurrence, text=text)


def say(text: str) -> Say:
    return Say(kind=ActionKind.say, text=text)


def link(arrow_id: str, card_id: str, dst: str, text: str = "", quote: str = "", occurrence: int | None = None) -> Link:
    return Link(kind=ActionKind.link, id=arrow_id, card=card_id, quote=quote, occurrence=occurrence, dst=dst, text=text)


def unlink(arrow_id: str) -> Unlink:
    return Unlink(kind=ActionKind.unlink, id=arrow_id)


def move(card_id: str, x: float, y: float) -> Move:
    return Move(kind=ActionKind.move, id=card_id, x=x, y=y)


def resize(card_id: str, width: float | None = None, height: float | None = None) -> Resize:
    return Resize(kind=ActionKind.resize, id=card_id, width=width, height=height)


def place(card_id: str, x: float, y: float) -> Place:
    return Place(kind=ActionKind.place, id=card_id, x=x, y=y)


def clear() -> Clear:
    return Clear(kind=ActionKind.clear)


def send() -> Send:
    return Send(kind=ActionKind.send)


def as_json(*bodies: TBody) -> list[dict[str, Any]]:
    """The actions as an MCP client sends them."""
    return [body.model_dump(mode="json") for body in bodies]


async def read_changes(client: Client[Any]) -> Board:
    """The board that read_changes returns."""
    return Board.model_validate((await client.call_tool("read_changes", {"name": BOARD})).structured_content)


async def read_board(client: Client[Any], *, history: bool = False, **params: Any) -> Board:
    """The board that read returns."""
    return Board.model_validate(
        (await client.call_tool("read", {"name": BOARD, "history": history, **params})).structured_content
    )
