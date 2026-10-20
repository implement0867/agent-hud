import asyncio
from collections.abc import AsyncIterator

from agent_hud.models.board import Board
from agent_hud.models.ops import Op
from agent_hud.models.view import Turn, View


class BoardStore:
    """The one owner of the board, the agent's waits and the user's sent messages, on the event loop. Readers get copies."""

    def __init__(self) -> None:
        self._board = Board()
        self._waits = 0
        self._changed = asyncio.Event()
        self._messages: list[str] = []
        self._message_added = asyncio.Event()

    def read(self) -> Board:
        return self._board.model_copy(deep=True)

    def view(self) -> View:
        return View(board=self.read(), turn=Turn.user if self._waits else Turn.agent)

    def apply(self, ops: list[Op]) -> None:
        self._board.apply(ops)
        self._notify()

    async def watch(self) -> AsyncIterator[View]:
        """The view now, then again after each change."""
        while True:
            changed = self._changed
            yield self.view()
            await changed.wait()

    def add_message(self, message: str) -> None:
        self._messages.append(message)
        self._message_added.set()

    async def wait_for_messages(self) -> list[str]:
        """The messages sent since the last call. Waits for one when there are none."""
        self._waits += 1
        self._notify()
        try:
            await self._message_added.wait()
        finally:
            self._waits -= 1
            self._notify()
        self._message_added.clear()
        messages, self._messages = self._messages, []
        return messages

    def _notify(self) -> None:
        self._changed.set()
        self._changed = asyncio.Event()
