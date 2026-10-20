import asyncio
from collections.abc import AsyncIterator

from agent_hud.models.board import Board
from agent_hud.models.ops import Op


class BoardStore:
    """The one owner of the board and of the user's sent messages, on the event loop. Readers get copies."""

    def __init__(self) -> None:
        self._board = Board()
        self._changed = asyncio.Event()
        self._messages: list[str] = []
        self._message_added = asyncio.Event()

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

    def add_message(self, message: str) -> None:
        self._messages.append(message)
        self._message_added.set()

    async def wait_for_messages(self) -> list[str]:
        """The messages sent since the last call. Waits for one when there are none."""
        await self._message_added.wait()
        self._message_added.clear()
        messages, self._messages = self._messages, []
        return messages
