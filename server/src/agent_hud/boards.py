from pathlib import Path
from typing import Annotated

from pydantic import Field, StringConstraints, TypeAdapter

from agent_hud.hud import Hud
from agent_hud.models.base import Model
from agent_hud.models.events import AgentState

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


def open_hud(huds: dict[TBoardName, Hud], directory: Path, name: TBoardName) -> Hud:
    """The hud of the board, opened into huds on first use. ValueError when the directory has no state file for it."""
    if name not in huds:
        path = directory / f"{name}.db"
        if not path.exists():
            raise ValueError(
                f"no board '{name}': the boards are {', '.join(board_names(directory)) or 'none'}; create_board makes one"
            )
        huds[name] = Hud(path)
    return huds[name]


def summarize(name: TBoardName, hud: Hud) -> BoardSummary:
    return BoardSummary(name=name, card_count=len(hud.board.cards), agent=hud.snapshot().agent)
