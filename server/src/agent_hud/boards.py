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
"""The name of one board. It is also the stem of the board's state file."""


class BoardSummary(Model):
    """One board as the list of boards shows it."""

    name: TBoardName
    cards: int = Field(description="The number of cards on the board")
    agent: AgentState


def open_boards(directory: Path) -> dict[TBoardName, Hud]:
    """
    The hud of each board whose state file is in the directory, by name.
    ValidationError when a file's stem is not a board name.
    """
    name = TypeAdapter[TBoardName](TBoardName)
    return {name.validate_python(path.stem): Hud(path) for path in sorted(directory.glob("*.db"))}


def summarize(name: TBoardName, hud: Hud) -> BoardSummary:
    return BoardSummary(name=name, cards=len(hud.board.cards), agent=hud.snapshot().agent)
