"""Shared fixtures keep the Pydantic models and the UI's Zod schemas in step.

`protocol/fixtures/server.json` is generated here; set AGENT_HUD_UPDATE_FIXTURES=1 to rewrite it.
The UI test suite parses both files with its Zod schemas.
"""

import json
import os
from pathlib import Path
from typing import Any

import pytest

from agent_hud.board import Board
from agent_hud.demo import seed
from agent_hud.protocol import (
    ErrorMsg,
    GoneMsg,
    ServerType,
    Status,
    StatusMsg,
    client_messages,
    server_messages,
)
from tests.conftest import Act, Write, anchor


def _fixtures() -> Path:
    return Path(__file__).resolve().parents[2] / "protocol" / "fixtures"


def _server_messages(board: Board, write: Write, act: Act) -> list[dict[str, Any]]:
    seed(board)
    for label, reaction in [("plan.3", "approve"), ("plan.4", "approve"), ("plan.2", "question")]:
        el_id, key = anchor(board, label)
        act(t="react", id=el_id, anchor=key, reaction=reaction)
    act(t="comment", id="plan", anchor=anchor(board, "plan.2")[1], text="Wording is unclear")
    write({"op": "reply", "at": "plan.2", "text": "Batches of 10k rows; see risk card"})
    act(t="edit", id="opts", anchor=anchor(board, "opts.r1.pick")[1], value=True)
    act(t="edit", id="opts", anchor=anchor(board, "opts.r2.notes")[1], value="no ordering")
    act(t="add", id="opts", value="NATS")
    act(t="note", x=640, y=420, text="Consider **rollback**")
    act(
        t="link",
        src={"id": "plan", "anchor": anchor(board, "plan.6")[1]},
        dst={"id": "plan", "anchor": anchor(board, "plan.1")[1]},
        text="entails?",
    )
    act(t="place", id="plan", x=40, y=40)
    act(t="resize", id="plan", w=460)
    messages = [
        board.hello(),
        StatusMsg(t=ServerType.STATUS, status=Status(waiting=True, pending=3, viewers=2)),
        GoneMsg(t=ServerType.GONE, id="risk"),
        ErrorMsg(t=ServerType.ERROR, message="plan has no item 'k99'"),
    ]
    return [json.loads(m.model_dump_json()) for m in messages]


def test_server_fixture_is_current(board: Board, write: Write, act: Act) -> None:
    generated = _server_messages(board, write, act)
    path = _fixtures() / "server.json"
    if os.environ.get("AGENT_HUD_UPDATE_FIXTURES") == "1":
        path.write_text(json.dumps(generated, indent=2) + "\n")
    assert json.loads(path.read_text()) == generated, "run with AGENT_HUD_UPDATE_FIXTURES=1 and commit"
    for msg in generated:
        server_messages().validate_python(msg)


@pytest.mark.parametrize("msg", json.loads((_fixtures() / "client.json").read_text()), ids=lambda m: m["t"])
def test_client_fixture_validates(msg: dict[str, Any]) -> None:
    assert client_messages().validate_python(msg).t == msg["t"]
