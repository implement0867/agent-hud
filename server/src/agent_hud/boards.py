from pathlib import Path
from typing import Annotated

from pydantic import Field, StringConstraints, TypeAdapter, ValidationError

from agent_hud.exchange import Exchange
from agent_hud.models.base import Model
from agent_hud.models.events import AgentState
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


def board_names(directory: Path) -> list[TBoardName]:
    """The name of each board: the stem of each state file in the directory. ValidationError when one is not a name."""
    return sorted(BoardNameAdapter.validate_python(path.stem) for path in directory.glob("*.db"))


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


def open_exchange(exchanges: dict[TBoardName, Exchange], directory: Path, name: TBoardName) -> Exchange:
    """The exchange of the board, opened into exchanges on first use. ValueError when the directory has no state file for it."""
    if name not in exchanges:
        path = directory / f"{name}.db"
        if not path.exists():
            raise ValueError(
                f"no board '{name}': the boards are {', '.join(board_names(directory)) or 'none'}; create_board makes one"
            )
        exchanges[name] = exchange_on_file(path)
    return exchanges[name]


def summarize(name: TBoardName, exchange: Exchange) -> BoardSummary:
    return BoardSummary(name=name, card_count=len(exchange.board.cards), agent=exchange.snapshot().agent)
