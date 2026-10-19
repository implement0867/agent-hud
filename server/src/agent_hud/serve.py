"""Canvas without MCP: for UI work and browser tests. The agent side is driven over `/debug/*`."""

from pathlib import Path

from agent_hud.board import Board
from agent_hud.browser import open_browser
from agent_hud.demo import seed
from agent_hud.persist import Persistence
from agent_hud.settings import HudSettings
from agent_hud.web import CanvasServer


async def serve(settings: HudSettings) -> None:
    board = Board(project=Path.cwd().name)
    if settings.state_file is not None:
        persistence = Persistence(board, settings.state_file)
        persistence.load()
        persistence.attach()
    if settings.demo:
        seed(board)
    canvas = CanvasServer(board, settings, debug_api=True)
    url = await canvas.ensure_started()
    if settings.open_browser:
        open_browser(url)
    await canvas.serve_forever()
