from typing import Annotated

from pydantic import Field, StringConstraints
from sqlalchemy import Engine, delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from agent_hud.exchange import Exchange
from agent_hud.models.base import Model
from agent_hud.models.board import Board
from agent_hud.models.events import AgentState
from agent_hud.tables import BoardRow

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


def board_names(engine: Engine) -> list[TBoardName]:
    """The name of each board, in order."""
    with Session(engine) as session:
        return list(session.scalars(select(BoardRow.name).order_by(BoardRow.name)))


def add_board(engine: Engine, name: TBoardName) -> None:
    """Add an empty board with the name. ValueError when a board has the name."""
    try:
        with Session(engine) as session, session.begin():
            session.add(BoardRow(name=name, checkpoint_seq=0, checkpoint=Board(), agent_seq=0))
    except IntegrityError as error:
        raise ValueError(f"a board '{name}' exists") from error


def remove_board(engine: Engine, name: TBoardName) -> None:
    """Delete the board and its actions, for good."""
    with Session(engine) as session, session.begin():
        session.execute(delete(BoardRow).where(BoardRow.name == name))


def summarize(name: TBoardName, exchange: Exchange) -> BoardSummary:
    return BoardSummary(name=name, card_count=len(exchange.board.cards), agent=exchange.snapshot().agent)
