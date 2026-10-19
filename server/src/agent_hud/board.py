from pathlib import Path

from agent_hud.demo import seed
from agent_hud.hub import Hub
from agent_hud.persist import Persistence
from agent_hud.settings import HudSettings
from agent_hud.state import BoardState


def open_board(settings: HudSettings) -> Hub:
    hub = Hub(BoardState(), project=Path.cwd().name)
    if settings.state_file is not None:
        Persistence(settings.state_file).attach(hub)
    if settings.demo:
        seed(hub.state)
    return hub
