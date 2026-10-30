from collections.abc import Iterable

from pydantic import TypeAdapter
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from agent_hud.boards import TBoardName
from agent_hud.models.actions import TActionId
from agent_hud.models.events import TTurnActionBody, Turn
from agent_hud.tables import TurnRow

TurnActionBodiesAdapter = TypeAdapter[tuple[TTurnActionBody, ...]](tuple[TTurnActionBody, ...])


def add_turn(session: Session, name: TBoardName, turn: Turn) -> None:
    """Add the turn after the board's other turns, for the monitors to get."""
    session.add(TurnRow(board=name, id=turn.id, actions=TurnActionBodiesAdapter.dump_json(turn.actions).decode()))


def list_turns(session: Session, name: TBoardName) -> list[Turn]:
    """The board's turns that some open monitor has not had, oldest first."""
    rows = session.scalars(select(TurnRow).where(TurnRow.board == name).order_by(TurnRow.seq))
    return [Turn(id=row.id, actions=TurnActionBodiesAdapter.validate_json(row.actions)) for row in rows]


def remove_turns(session: Session, name: TBoardName, turn_ids: Iterable[TActionId]) -> None:
    """Remove the board's turns with the ids, which every open monitor has had."""
    session.execute(delete(TurnRow).where(TurnRow.board == name, TurnRow.id.in_(turn_ids)))
