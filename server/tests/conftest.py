from collections.abc import Callable
from typing import Any

import pytest
from pydantic import TypeAdapter

from agent_hud.agent import apply
from agent_hud.hub import Hub
from agent_hud.ops import Op
from agent_hud.page import handle
from agent_hud.protocol import ClientMessage
from agent_hud.state import BoardState

type Write = Callable[..., None]
type Act = Callable[..., None]


@pytest.fixture
def hub() -> Hub:
    return Hub(BoardState(), project="test")


@pytest.fixture
def write(hub: Hub) -> Write:
    """Apply agent ops given as plain dicts, as the MCP tool receives them."""

    def _write(*ops: dict[str, Any]) -> None:
        hub.state, delta = apply(hub.state, TypeAdapter(list[Op]).validate_python(list(ops)))
        hub.publish(delta)

    return _write


@pytest.fixture
def act(hub: Hub) -> Act:
    """Apply a page message given as a plain dict, as the websocket receives it."""

    def _act(**msg: Any) -> None:
        hub.publish(handle(hub.state, ClientMessage.model_validate(msg).root))

    return _act


def anchor(hub: Hub, label: str) -> tuple[str, str]:
    el, key = hub.state.resolve(label)
    return el.id, key
