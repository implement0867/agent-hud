import asyncio
from pathlib import Path

from agent_hud.hub import Hub
from agent_hud.persist import Persistence
from agent_hud.report import report, show_cards
from agent_hud.server import build
from agent_hud.settings import HudSettings
from agent_hud.state import BoardState
from tests.conftest import Act, Write


async def test_board_survives_a_restart(hub: Hub, write: Write, act: Act, tmp_path: Path) -> None:
    path = tmp_path / "state" / "board.json"
    Persistence(path, delay=0.01).attach(hub)
    write({"op": "put", "id": "plan", "md": "1. a\n2. b"})
    act(t="react", id="plan", anchor="", reaction="approve")
    await asyncio.sleep(0.05)

    restored = Hub(BoardState(), project="test")
    Persistence(path).attach(restored)
    assert show_cards(restored.state, ["*"]) == show_cards(hub.state, ["*"])
    assert report(restored.state) == "plan approve", "unread changes survive too"


def test_missing_file_starts_empty(hub: Hub, tmp_path: Path) -> None:
    Persistence(tmp_path / "none.json").attach(hub)
    assert hub.state.elements == {}


def test_demo_with_a_state_file_starts_outside_an_event_loop(tmp_path: Path) -> None:
    build(HudSettings(demo=True, state_file=tmp_path / "board.json", open_browser=False, port=0))
