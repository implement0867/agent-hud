from typing import Annotated, Any

from fastmcp import Client
from pydantic import Discriminator, TypeAdapter

from agent_hud.models.board import Board
from agent_hud.models.events import EventKind, MessageReceived, MessageSent, ViewChanged
from agent_hud.models.ops import Op, OpKind, PutOp, RemoveOp


def put(card_id: str, md: str) -> PutOp:
    return PutOp(op=OpKind.put, id=card_id, md=md)


def remove(card_id: str) -> RemoveOp:
    return RemoveOp(op=OpKind.remove, id=card_id)


def as_json(*ops: Op) -> list[dict[str, Any]]:
    """The ops as an MCP client sends them."""
    return [op.model_dump(mode="json") for op in ops]


async def read_board(client: Client[Any]) -> Board:
    return Board.model_validate((await client.call_tool("read", {})).structured_content)


def sent(message: str) -> str:
    """The event a page sends for the message."""
    return MessageSent(kind=EventKind.message_sent, message=message).model_dump_json()


def page_event(text: str) -> ViewChanged | MessageReceived:
    """An event that the server sends to a page."""
    return TypeAdapter(Annotated[ViewChanged | MessageReceived, Discriminator("kind")]).validate_json(text)
