from collections.abc import Callable
from typing import Any

import pytest

from agent_hud.board import Board
from agent_hud.ops import op_list
from agent_hud.protocol import client_messages

type Write = Callable[..., None]
type Act = Callable[..., None]


@pytest.fixture
def board() -> Board:
    return Board(project="test")


@pytest.fixture
def write(board: Board) -> Write:
    """Apply agent ops given as plain dicts, as the MCP tool receives them."""

    def _write(*ops: dict[str, Any]) -> None:
        board.apply(op_list().validate_python(list(ops)))

    return _write


@pytest.fixture
def act(board: Board) -> Act:
    """Apply a page message given as a plain dict, as the websocket receives it."""

    def _act(**msg: Any) -> None:
        board.handle(client_messages().validate_python(msg))

    return _act


def anchor(board: Board, label: str) -> tuple[str, str]:
    """Element id and anchor key for an agent label such as `plan.3`."""
    el_id, _, suffix = label.partition(".")
    return el_id, board.elements[el_id].resolve(suffix)
