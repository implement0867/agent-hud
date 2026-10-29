from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from agent_hud.boards import TBoardName
from agent_hud.exchange import Exchange
from agent_hud.models.state import BoardState
from agent_hud.tables import BoardRow


def list_board_names(session: Session) -> list[TBoardName]:
    """List the name of each board."""
    return list(session.scalars(select(BoardRow.name)))


def add_board(session: Session, name: TBoardName) -> None:
    """Add an empty board with the name. ValueError when a board has the name."""
    if session.get(BoardRow, name) is not None:
        raise ValueError(f"a board '{name}' exists")
    session.add(BoardRow(name=name))


def remove_board(session: Session, name: TBoardName) -> None:
    """Remove the board."""
    session.execute(delete(BoardRow).where(BoardRow.name == name))


def load_board_state(session: Session, name: TBoardName) -> BoardState:
    """Load the state of the board."""
    return session.get_one(BoardRow, name).state


def save_exchange(session: Session, exchange: Exchange) -> None:
    """Save the state of the exchange's board, and commit."""
    session.execute(update(BoardRow).where(BoardRow.name == exchange.name).values(state=exchange.state))
    session.commit()
