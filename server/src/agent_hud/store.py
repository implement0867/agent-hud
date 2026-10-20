import asyncio
from collections.abc import AsyncIterator

from agent_hud.models.board import Board
from agent_hud.models.ops import Op


class BoardStore:
    """The one owner of the board. Readers get copies, and every change goes through apply on the event loop."""

    def __init__(self) -> None:
        self._board = Board()
        self._changed = asyncio.Event()

    def read(self) -> Board:
        return self._board.model_copy(deep=True)

    def apply(self, ops: list[Op]) -> None:
        self._board.apply(ops)
        self._changed.set()
        self._changed = asyncio.Event()

    async def watch(self) -> AsyncIterator[Board]:
        """The board now, then again after each change."""
        while True:
            changed = self._changed
            yield self.read()
            await changed.wait()
