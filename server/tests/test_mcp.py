import asyncio
import json

import pytest
from fastmcp import Client
from websockets.asyncio.client import connect
from websockets.typing import Origin

from agent_hud.board import Board
from agent_hud.server import build
from agent_hud.settings import HudSettings
from tests.conftest import Act, anchor


@pytest.fixture
def settings() -> HudSettings:
    return HudSettings(port=0, open_browser=False)


def _text(result: object) -> str:
    content = getattr(result, "content", [])
    return "".join(getattr(block, "text", "") for block in content)


async def test_tool_schemas_stay_small(board: Board, settings: HudSettings) -> None:
    async with Client(build(settings, board)) as client:
        tools = {t.name: t for t in await client.list_tools()}
    assert set(tools) == {"write", "read"}
    size = sum(len(json.dumps(t.input_schema)) + len(t.description or "") for t in tools.values())
    assert size < 4500, f"tool definitions cost {size} chars on every turn"
    assert all(t.output_schema is None for t in tools.values()), "no duplicate structured output"


async def test_write_then_wait_for_send(board: Board, settings: HudSettings, act: Act) -> None:
    async with Client(build(settings, board)) as client:
        result = await client.call_tool("write", {"ops": [{"op": "put", "id": "plan", "md": "1. a\n2. b"}]})
        assert _text(result).startswith("ok\n(no canvas tab is open")

        async def user() -> None:
            await asyncio.sleep(0.05)
            el_id, key = anchor(board, "plan.1")
            act(t="react", id=el_id, anchor=key, reaction="reject")
            act(t="submit", message="redo 1")

        board.subscribe(lambda _: None)  # a canvas tab
        reviewer = asyncio.create_task(user())
        result = await client.call_tool("read", {"wait": 5})
        await reviewer
    assert _text(result).splitlines()[:2] == ["plan.1 reject", 'submit "redo 1"']


async def test_wait_without_send_times_out_and_keeps_changes(board: Board, settings: HudSettings, act: Act) -> None:
    settings.max_wait = 1
    async with Client(build(settings, board)) as client:
        await client.call_tool("write", {"ops": [{"op": "put", "id": "t", "md": "hi"}]})
        act(t="react", id="t", anchor="", reaction="approve")
        board.subscribe(lambda _: None)  # a canvas tab
        first = await client.call_tool("read", {"wait": 30})
        second = await client.call_tool("read", {})
    assert _text(first).startswith("no Send within 30s; 1 unread changes")
    assert _text(second).startswith("t approve")


async def test_browser_tab_round_trip_over_a_real_socket(board: Board, settings: HudSettings) -> None:
    async with Client(build(settings, board)) as client:
        result = await client.call_tool("write", {"ops": [{"op": "put", "id": "plan", "md": "1. a\n2. b"}]})
        url = _text(result).split("open ")[1].rstrip(")")
        origin = Origin(url.rstrip("/"))
        async with connect(url.replace("http", "ws") + "ws", origin=origin) as ws:
            hello = json.loads(await ws.recv())
            assert hello["elements"][0]["id"] == "plan"
            key = hello["elements"][0]["items"][1]["id"]
            await ws.send(json.dumps({"t": "comment", "id": "plan", "anchor": key, "text": "why?"}))
            await ws.send(json.dumps({"t": "submit", "message": None}))
            result = await client.call_tool("read", {"wait": 5})
            assert _text(result) == 'plan.2 "why?"\nsubmit'


async def test_wait_without_a_tab_returns_quickly(
    board: Board, settings: HudSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def no_tab(_: float) -> bool:
        return False

    monkeypatch.setattr(board, "wait_for_viewer", no_tab)
    async with Client(build(settings, board)) as client:
        result = await client.call_tool("read", {"wait": 600})
    assert _text(result).startswith("no canvas tab is open, so nobody can press Send")


async def test_open_hint_is_not_repeated(board: Board, settings: HudSettings) -> None:
    async with Client(build(settings, board)) as client:
        first = await client.call_tool("write", {"ops": [{"op": "put", "id": "t", "md": "hi"}]})
        second = await client.call_tool("write", {"ops": [{"op": "set", "at": "t", "value": "hey"}]})
    assert "no canvas tab is open" in _text(first)
    assert _text(second) == "ok"
