import asyncio
import sys

from websockets.asyncio.client import connect


async def follow(url: str) -> None:
    """Print each turn that the websocket sends, one line each, until it closes."""
    async with connect(url, proxy=None) as monitor:
        async for line in monitor:
            print(line, flush=True)


def main() -> None:
    """agent-hud-turns URL: the turns of the user as lines on stdout, for a monitor that takes a command."""
    match sys.argv[1:]:
        case [url]:
            asyncio.run(follow(url))
        case _:
            sys.exit("usage: agent-hud-turns URL")


if __name__ == "__main__":
    main()
