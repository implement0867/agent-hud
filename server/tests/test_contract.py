import json
import os
from pathlib import Path
from typing import Any

import pytest
from pydantic import TypeAdapter

from agent_hud.demo import seed
from agent_hud.hub import Hub
from agent_hud.protocol import ErrorMsg, GoneMsg, ServerMsg, ServerType, Status, StatusMsg, client_messages
from tests.conftest import Act, Write, anchor


def _fixtures() -> Path:
    return Path(__file__).resolve().parents[2] / "protocol" / "fixtures"


def _server_messages(hub: Hub, write: Write, act: Act) -> list[dict[str, Any]]:
    seed(hub.state)
    for label, reaction in [("plan.3", "approve"), ("plan.4", "approve"), ("plan.2", "question")]:
        el_id, key = anchor(hub, label)
        act(t="react", id=el_id, anchor=key, reaction=reaction)
    act(t="comment", id="plan", anchor=anchor(hub, "plan.2")[1], text="Wording is unclear")
    write({"op": "reply", "at": "plan.2", "text": "Batches of 10k rows; see risk card"})
    act(t="edit", id="opts", anchor=anchor(hub, "opts.r1.pick")[1], value=True)
    act(t="edit", id="opts", anchor=anchor(hub, "opts.r2.notes")[1], value="no ordering")
    act(t="add", id="opts", value="NATS")
    act(t="note", x=640, y=420, text="Consider **rollback**")
    act(
        t="link",
        src={"id": "plan", "anchor": anchor(hub, "plan.6")[1]},
        dst={"id": "plan", "anchor": anchor(hub, "plan.1")[1]},
        text="entails?",
    )
    act(t="place", id="plan", x=40, y=40)
    act(t="resize", id="plan", w=460)
    messages = [
        hub.hello(),
        StatusMsg(t=ServerType.STATUS, status=Status(waiting=True, pending=3, viewers=2)),
        GoneMsg(t=ServerType.GONE, id="risk"),
        ErrorMsg(t=ServerType.ERROR, message="plan has no item 'k99'"),
    ]
    return [json.loads(m.model_dump_json()) for m in messages]


def test_server_fixture_is_current(hub: Hub, write: Write, act: Act) -> None:
    """Pydantic and the UI's Zod schemas both parse `protocol/fixtures/`; set AGENT_HUD_UPDATE_FIXTURES=1 to rewrite."""
    generated = _server_messages(hub, write, act)
    path = _fixtures() / "server.json"
    if os.environ.get("AGENT_HUD_UPDATE_FIXTURES") == "1":
        path.write_text(json.dumps(generated, indent=2) + "\n")
    assert json.loads(path.read_text()) == generated, "run with AGENT_HUD_UPDATE_FIXTURES=1 and commit"
    for msg in generated:
        TypeAdapter(ServerMsg).validate_python(msg)


@pytest.mark.parametrize("msg", json.loads((_fixtures() / "client.json").read_text()), ids=lambda m: m["t"])
def test_client_fixture_validates(msg: dict[str, Any]) -> None:
    assert client_messages().validate_python(msg).t == msg["t"]
