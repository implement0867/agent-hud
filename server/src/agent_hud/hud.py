from collections.abc import AsyncIterator
from functools import reduce

from agent_hud.log import Log
from agent_hud.models.actions import Action, Author
from agent_hud.models.board import Board


class Hud:
    """The board, and the log of the actions that made it."""

    def __init__(self) -> None:
        self.board = Board()
        self.log = Log()
        self._agent_read = 0

    def act(self, actions: list[Action]) -> None:
        """Apply the actions in order, all or nothing. ValueError if one does not fit the board."""
        self.board = reduce(Board.apply, actions, self.board)
        self.log.extend(actions)

    async def boards(self) -> AsyncIterator[Board]:
        """The board now, then again after each change."""
        board = self.board
        yield board
        async for _ in self.log.follow(len(self.log.actions)):
            if self.board != board:
                board = self.board
                yield board

    async def user_actions(self) -> AsyncIterator[Action]:
        """The user's actions that no agent has had yet, then each new one."""
        start = self._agent_read
        async for batch in self.log.follow(start):
            start += len(batch)
            self._agent_read = max(self._agent_read, start)
            for action in batch:
                if action.author is Author.user:
                    yield action
