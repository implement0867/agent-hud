from typing import Any

from fastmcp import Client

from agent_hud.models.board import Board
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
