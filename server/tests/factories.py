from typing import Any

from fastmcp import Client

from agent_hud.models.actions import (
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

# The board that the tests' tools and sockets name.
BOARD = "test"


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
