from sqlalchemy import Engine, delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from agent_hud.boards import TBoardName
from agent_hud.tables import BoardRow


def select_board_names(engine: Engine) -> list[TBoardName]:
    """Select the name of each board."""
    with Session(engine) as session:
        return list(session.scalars(select(BoardRow.name)))


def add_board(engine: Engine, name: TBoardName) -> None:
    """Add an empty board with the name. ValueError when a board has the name."""
    try:
        with Session(engine) as session, session.begin():
            session.add(BoardRow(name=name))
    except IntegrityError as error:
        raise ValueError(f"a board '{name}' exists") from error


def remove_board(engine: Engine, name: TBoardName) -> None:
    """Delete the board and its actions."""
    with Session(engine) as session, session.begin():
        session.execute(delete(BoardRow).where(BoardRow.name == name))
