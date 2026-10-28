from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Protocol

from agent_hud.boards import TBoardName
from agent_hud.models.state import BoardState


class Store(Protocol):
    """The state of each board. The changes are durable once committed."""

    def list_board_names(self) -> list[TBoardName]:
        """List the name of each board."""
        ...

    def add_board(self, name: TBoardName) -> None:
        """Add an empty board with the name. ValueError when a board has the name."""
        ...

    def remove_board(self, name: TBoardName) -> None:
        """Remove the board."""
        ...

    def load_board_state(self, name: TBoardName) -> BoardState:
        """Load the state of the board."""
        ...

    def save_board_state(self, name: TBoardName, state: BoardState) -> None:
        """Save the state of the board."""
        ...

    def commit(self) -> None:
        """Make the changes since the last commit durable."""
        ...


type StoreFactory = Callable[[], AbstractContextManager[Store]]
"""Open a store for one request or one message; the changes that it does not commit are lost when it closes."""
