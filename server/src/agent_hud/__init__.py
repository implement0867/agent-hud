import asyncio
import logging
import sys

from pydantic_settings import CliApp

from agent_hud.settings import HudSettings, Mode


def main() -> None:
    """Entry point: MCP over stdio by default, `--mode serve` for the canvas alone."""
    settings = CliApp.run(HudSettings)
    logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="agent-hud %(levelname)s %(message)s")
    match settings.mode:
        case Mode.MCP:
            from agent_hud.server import build

            build(settings).run(transport="stdio", show_banner=False)
        case Mode.SERVE:
            from agent_hud.serve import serve

            asyncio.run(serve(settings))
