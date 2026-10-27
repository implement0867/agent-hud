from pathlib import Path
from typing import Annotated

from pydantic import Field, StringConstraints, TypeAdapter, ValidationError

from agent_hud.exchange import Exchange
from agent_hud.models.base import Model
from agent_hud.models.events import AgentState
from agent_hud.settings import Settings
from agent_hud.store import SqliteStore

type TBoardName = Annotated[
    str,
    StringConstraints(pattern=r"^[A-Za-z0-9_-]{1,64}$"),
    Field(description="The name of a board: 1 to 64 letters, digits, _ or -"),
]

BoardNameAdapter = TypeAdapter[TBoardName](TBoardName)


class BoardSummary(Model):
    """One board as the list of boards shows it."""

    name: TBoardName
    card_count: int = Field(description="The number of cards on the board")
    agent: AgentState


def exchange_on_file(path: Path) -> Exchange:
    """
    The exchange on the SQLite state file at the path. RuntimeError when another process holds the file.
    ValidationError when the file does not fit this version.
    """
    store = SqliteStore(path)
    try:
        return Exchange(store)
    except ValidationError:
        store.close()
        raise


class Boards:
    """
    The boards in the settings' boards dir, each a state file named for the board, and the exchange of each board
    that is open, which opens on first use and stays open until the board is deleted or the boards close.
    """

    def __init__(self, settings: Settings, opened: dict[TBoardName, Exchange]) -> None:
        self.directory = settings.boards_dir
        self.opened = opened

    def names(self) -> list[TBoardName]:
        """The name of each board, in order. ValidationError when the stem of a state file is not a name."""
        return sorted(BoardNameAdapter.validate_python(path.stem) for path in self.directory.glob("*.db"))

    def get(self, name: TBoardName) -> Exchange:
        """The exchange of the board. ValueError when the boards dir has no state file for it."""
        if name not in self.opened:
            path = self.directory / f"{name}.db"
            if not path.exists():
                raise ValueError(
                    f"no board '{name}': the boards are {', '.join(self.names()) or 'none'}; create_board makes one"
                )
            self.opened[name] = exchange_on_file(path)
        return self.opened[name]

    def create(self, name: TBoardName) -> Exchange:
        """The exchange of a new, empty board. ValueError when a board has the name."""
        path = self.directory / f"{name}.db"
        if path.exists():
            raise ValueError(f"a board '{name}' exists")
        self.opened[name] = exchange_on_file(path)
        return self.opened[name]

    def delete(self, name: TBoardName) -> None:
        """
        Close the board and delete its state file, for good.
        ValueError when no board has the name, or when a monitor is open on it.
        """
        exchange = self.get(name)
        if exchange.monitors:
            raise ValueError(f"the board '{name}' has {exchange.monitors} open monitors: stop them first")
        exchange.close()
        del self.opened[name]
        (self.directory / f"{name}.db").unlink()

    def summary(self, name: TBoardName) -> BoardSummary:
        """The board with its card count and agent state. ValueError when no board has the name."""
        exchange = self.get(name)
        return BoardSummary(name=name, card_count=len(exchange.board.cards), agent=exchange.snapshot().agent)

    def close(self) -> None:
        """Compact the state file of each open board and let it go."""
        for exchange in self.opened.values():
            exchange.compact()
            exchange.close()
