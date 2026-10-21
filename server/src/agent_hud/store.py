import asyncio
from collections.abc import AsyncIterator, Generator
from contextlib import contextmanager

from agent_hud.models.board import Board
from agent_hud.models.card import Reaction, TCardId
from agent_hud.models.ops import TOp


class BoardStore:
    """The one owner of the board and of the user's sent messages, on the event loop. Readers get copies."""

    def __init__(self) -> None:
        self._board = Board()
        self._changed = asyncio.Event()
        self._messages: list[str] = []
        self._listeners: set[asyncio.Queue[str]] = set()

    def read(self) -> Board:
        return self._board.model_copy(deep=True)

    def apply(self, ops: list[TOp]) -> None:
        self._board.apply(ops)
        self._publish()

    def react(self, card_id: TCardId, reaction: Reaction | None) -> None:
        """Set the user's reaction on the card, if the agent has not removed it since the page showed it."""
        if card_id in self._board.cards:
            self._board.react(card_id, reaction)
            self._publish()

    def _publish(self) -> None:
        self._changed.set()
        self._changed = asyncio.Event()

    async def watch(self) -> AsyncIterator[Board]:
        """The board now, then again after each change."""
        while True:
            changed = self._changed
            yield self.read()
            await changed.wait()

    def add_message(self, message: str) -> None:
        if self._listeners:
            for listener in self._listeners:
                listener.put_nowait(message)
        else:
            self._messages.append(message)

    @contextmanager
    def listen(self) -> Generator[asyncio.Queue[str]]:
        """A queue of the messages sent while no one listened, then of each new message."""
        listener = asyncio.Queue[str]()
        for message in self._messages:
            listener.put_nowait(message)
        self._messages = []
        self._listeners.add(listener)
        try:
            yield listener
        finally:
            self._listeners.remove(listener)
