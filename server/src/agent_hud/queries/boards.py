from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from agent_hud.boards import TBoardName
from agent_hud.models.state import BoardState
from agent_hud.tables import BoardRow


def list_board_names(session: Session) -> list[TBoardName]:
    """List the name of each board."""
    return list(session.scalars(select(BoardRow.name)))


def check_board_exists(session: Session, name: TBoardName) -> bool:
    """Check whether a board has the name."""
    return session.get(BoardRow, name) is not None


def add_board(session: Session, name: TBoardName) -> None:
    """Add an empty board with the name. ValueError when a board has the name."""
    if check_board_exists(session, name):
        raise ValueError(f"a board '{name}' exists")
    session.add(BoardRow(name=name))


def remove_board(session: Session, name: TBoardName) -> None:
    """Remove the board."""
    session.execute(delete(BoardRow).where(BoardRow.name == name))


def load_board_state(session: Session, name: TBoardName) -> BoardState:
    """Load the state of the board. ValidationError when the row holds a state that this version does not take."""
    return BoardState.model_validate_json(session.get_one(BoardRow, name).state)


def commit_board_state(session: Session, name: TBoardName, state: BoardState) -> None:
    """Save the state of the board, and commit."""
    session.execute(update(BoardRow).where(BoardRow.name == name).values(state=state.model_dump_json()))
    session.commit()
