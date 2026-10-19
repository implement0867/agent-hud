from agent_hud.board import open_board
from agent_hud.browser import open_browser
from agent_hud.settings import HudSettings
from agent_hud.web import CanvasServer


async def serve(settings: HudSettings) -> None:
    """Canvas without MCP, for UI work and browser tests; `/debug/*` drives the agent side."""
    canvas = CanvasServer(open_board(settings), settings, debug_api=True)
    url = await canvas.ensure_started()
    if settings.open_browser:
        open_browser(url)
    await canvas.serve_forever()
