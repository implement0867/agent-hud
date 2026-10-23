from typing import Any

from fastmcp import Client

from agent_hud.models.actions import (
    ActionKind,
    Clear,
    Comment,
    Fill,
    Link,
    Move,
    Put,
    React,
    Reaction,
    Remove,
    Say,
    Send,
    TBody,
    TValue,
    Unlink,
    Unreact,
)
from agent_hud.models.board import Board
from agent_hud.server import Reading


def put(card_id: str, md: str) -> Put:
    return Put(kind=ActionKind.put, id=card_id, md=md)


def remove(card_id: str) -> Remove:
    return Remove(kind=ActionKind.remove, id=card_id)


def react(ref: str, reaction: Reaction) -> React:
    return React(kind=ActionKind.react, ref=ref, reaction=reaction)


def unreact(ref: str) -> Unreact:
    return Unreact(kind=ActionKind.unreact, ref=ref)


def comment(ref: str, text: str) -> Comment:
    return Comment(kind=ActionKind.comment, ref=ref, text=text)


def say(text: str) -> Say:
    return Say(kind=ActionKind.say, text=text)


def fill(ref: str, value: TValue) -> Fill:
    return Fill(kind=ActionKind.fill, ref=ref, value=value)


def link(arrow_id: str, src: str, dst: str, text: str = "") -> Link:
    return Link(kind=ActionKind.link, id=arrow_id, src=src, dst=dst, text=text)


def unlink(arrow_id: str) -> Unlink:
    return Unlink(kind=ActionKind.unlink, id=arrow_id)


def move(card_id: str, x: float, y: float) -> Move:
    return Move(kind=ActionKind.move, id=card_id, x=x, y=y)


def clear() -> Clear:
    return Clear(kind=ActionKind.clear)


def send() -> Send:
    return Send(kind=ActionKind.send)


def as_json(*bodies: TBody) -> list[dict[str, Any]]:
    """The actions as an MCP client sends them."""
    return [body.model_dump(mode="json") for body in bodies]


async def read(client: Client[Any], *, history: bool = False) -> Reading:
    return Reading.model_validate((await client.call_tool("read", {"history": history})).structured_content)


async def read_board(client: Client[Any], *, history: bool = False, **params: Any) -> Board:
    """The board that read returns, without the parts, to compare with the hud's board."""
    reading = Reading.model_validate(
        (await client.call_tool("read", {"history": history, **params})).structured_content
    )
    return Board.model_validate(reading.model_dump(exclude={"parts"}))
