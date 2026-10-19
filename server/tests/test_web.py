import json
from typing import Any

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from agent_hud.hub import Hub
from agent_hud.report import report
from agent_hud.settings import HudSettings
from agent_hud.web import create_app
from tests.conftest import Act, Write, anchor

ORIGIN = "http://localhost:5173"


@pytest.fixture
def client(hub: Hub) -> TestClient:
    settings = HudSettings(extra_origins=[ORIGIN], open_browser=False)
    return TestClient(create_app(hub, settings, debug_api=True, allowed_hosts=["testserver"]))


def _recv(ws: Any) -> dict[str, Any]:
    return json.loads(ws.receive_text())


def test_socket_sends_hello_then_live_updates(client: TestClient, hub: Hub, write: Write) -> None:
    write({"op": "put", "id": "plan", "md": "1. a\n2. b"})
    with client.websocket_connect("/ws", headers={"origin": ORIGIN}) as ws:
        hello = _recv(ws)
        assert hello["t"] == "hello"
        assert [el["id"] for el in hello["elements"]] == ["plan"]
        assert _recv(ws)["status"]["viewers"] == 1
        el_id, key = anchor(hub, "plan.2")
        ws.send_text(json.dumps({"t": "react", "id": el_id, "anchor": key, "reaction": "approve"}))
        upsert = _recv(ws)
        assert upsert["element"]["feedback"][key]["reaction"] == "approve"
        assert _recv(ws)["status"]["pending"] == 1
    assert report(hub.state) == "plan.2 approve"


@pytest.mark.parametrize(
    ("payload", "reason"),
    [
        ({"t": "react", "id": "plan", "anchor": "nope", "reaction": "approve"}, "no anchor"),
        ({"t": "shout"}, "bad message"),
        ({"t": "delete", "id": "plan"}, "belongs to the agent"),
    ],
)
def test_rejected_messages_come_back_as_errors(
    client: TestClient, write: Write, payload: dict[str, Any], reason: str
) -> None:
    write({"op": "put", "id": "plan", "md": "1. a"})
    with client.websocket_connect("/ws", headers={"origin": ORIGIN}) as ws:
        for _ in range(2):  # hello, status
            _recv(ws)
        ws.send_text(json.dumps(payload))
        error = _recv(ws)
        assert error["t"] == "error"
        assert reason in error["message"]


def test_foreign_origin_is_refused(client: TestClient) -> None:
    with (
        pytest.raises(WebSocketDisconnect),
        client.websocket_connect("/ws", headers={"origin": "https://evil.example"}),
    ):
        pass


def test_foreign_host_is_refused(client: TestClient) -> None:
    assert client.get("/", headers={"host": "evil.example"}).status_code == 400


@pytest.mark.parametrize(
    ("ops", "headers", "status"),
    [
        ([{"op": "put", "id": "t", "md": "hi"}], {}, 403),
        ([{"op": "put", "id": "t", "md": "hi"}], {"x-agent-hud": "1"}, 204),
        ([{"op": "set", "at": "ghost.1", "value": "x"}], {"x-agent-hud": "1"}, 400),
        ([{"op": "shout"}], {"x-agent-hud": "1"}, 422),
    ],
    ids=["no-header", "applied", "op-error", "invalid"],
)
def test_debug_write(client: TestClient, ops: list[dict[str, Any]], headers: dict[str, str], status: int) -> None:
    assert client.post("/debug/write", json=ops, headers=headers).status_code == status


def test_same_origin_page_may_connect(client: TestClient) -> None:
    with client.websocket_connect("/ws", headers={"origin": "http://testserver"}) as ws:
        assert _recv(ws)["t"] == "hello"


def test_debug_read_returns_the_agent_report(client: TestClient, write: Write, act: Act) -> None:
    write({"op": "put", "id": "plan", "md": "1. a"})
    act(t="submit", message=None)
    response = client.get("/debug/read", params={"show": "plan"}, headers={"x-agent-hud": "1"})
    assert response.text.splitlines()[:3] == ["submit", "", "plan: list"]
