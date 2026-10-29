from typing import Annotated

from pydantic import Field, StringConstraints

from agent_hud.models.base import Model
from agent_hud.models.events import AgentState
from agent_hud.models.state import BoardState

type TBoardName = Annotated[
    str,
    StringConstraints(pattern=r"^[A-Za-z0-9_-]{1,64}$"),
    Field(description="The name of a board: 1 to 64 letters, digits, _ or -"),
]


class BoardSummary(Model):
    """One board as the list of boards shows it."""

    name: TBoardName
    card_count: int = Field(description="The number of cards on the board")
    agent: AgentState


def summarize_board(name: TBoardName, state: BoardState, agent: AgentState) -> BoardSummary:
    """Summarize the board for the list of boards."""
    return BoardSummary(name=name, card_count=len(state.board.cards), agent=agent)
