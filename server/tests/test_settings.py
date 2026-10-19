from pathlib import Path

import pytest

from agent_hud.settings import HudSettings, packaged_ui


def test_ui_ships_inside_the_package() -> None:
    assert (packaged_ui() / "index.html").is_file(), "run `npm run build` in ui/"


def test_static_dir_can_be_overridden(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AGENT_HUD_STATIC_DIR", str(tmp_path))
    assert HudSettings().static_dir == tmp_path
