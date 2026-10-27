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


def open_boards(directory: Path) -> dict[TBoardName, Hud]:
    return {BoardNameAdapter.validate_python(path.stem): Hud(path) for path in sorted(directory.glob("*.db"))}


def summarize(name: TBoardName, hud: Hud) -> BoardSummary:
    return BoardSummary(name=name, card_count=len(hud.board.cards), agent=hud.snapshot().agent)
