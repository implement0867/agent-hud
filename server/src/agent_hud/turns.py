import asyncio
import sys

from websockets.asyncio.client import connect


async def print_frames(url: str) -> None:
    """Print each frame that the websocket sends, with its lines, until it closes."""
    async with connect(url, proxy=None) as monitor:
        async for frame in monitor:
            print(frame, flush=True)


def run_turns_command() -> None:
    """agent-hud-turns URL: the turns of the user as their lines on stdout, for a monitor that takes a command."""
    match sys.argv[1:]:
        case [url]:
            asyncio.run(print_frames(url))
        case _:
            sys.exit("usage: agent-hud-turns URL")


if __name__ == "__main__":
    run_turns_command()
