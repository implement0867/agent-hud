from typing import Any

from fastmcp import Client

from agent_hud.models.actions import (
    ActionKind,
    Comment,
    Put,
    React,
    Reaction,
    Remove,
    Say,
    TBody,
    Unreact,
)
from agent_hud.models.board import Board


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


def as_json(*bodies: TBody) -> list[dict[str, Any]]:
    """The actions as an MCP client sends them."""
    return [body.model_dump(mode="json") for body in bodies]


async def read_board(client: Client[Any]) -> Board:
    return Board.model_validate((await client.call_tool("read", {})).structured_content)
