import asyncio
from collections.abc import AsyncIterator

from agent_hud.models.actions import Action


class Log:
    """Every action in the order the board took it."""

    def __init__(self) -> None:
        self.actions: list[Action] = []
        self._grown = asyncio.Event()

    def extend(self, actions: list[Action]) -> None:
        self.actions.extend(actions)
        self._grown.set()
        self._grown = asyncio.Event()

    async def follow(self, start: int) -> AsyncIterator[list[Action]]:
        """The actions from start on, then each run of actions as the log grows."""
        while True:
            grown = self._grown
            if start < len(self.actions):
                batch = self.actions[start:]
                start += len(batch)
                yield batch
            else:
                await grown.wait()
