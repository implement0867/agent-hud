from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from agent_hud.boards import TBoardName
from agent_hud.models.board import Board
from agent_hud.models.cursor import ReadCursor
from agent_hud.models.draft import Draft
from agent_hud.tables import BoardRow, CursorRow


def list_board_names(session: Session) -> list[TBoardName]:
    return list(session.scalars(select(BoardRow.name)))


def count_cards_of_each_board(session: Session) -> dict[TBoardName, int]:
    """The number of cards on each board, by name, counted in the database."""
    cards = func.json_each(BoardRow.board, "$.cards").table_valued("key")
    card_count = select(func.count()).select_from(cards).scalar_subquery()
    return dict(session.execute(select(BoardRow.name, card_count)).all())


def check_board_exists(session: Session, name: TBoardName) -> bool:
    return session.get(BoardRow, name) is not None


def add_board(session: Session, name: TBoardName) -> None:
    """Add an empty board with the name, with an empty draft and a new cursor. ValueError when a board has the name."""
    if check_board_exists(session, name):
        raise ValueError(f"a board '{name}' exists")
    session.add(BoardRow(name=name, board=Board().model_dump_json(), draft=Draft().model_dump_json()))
    session.add(CursorRow(board=name, cursor=ReadCursor().model_dump_json()))


def remove_board(session: Session, name: TBoardName) -> None:
    """Remove the board, and with it its turns and its cursor."""
    session.execute(delete(BoardRow).where(BoardRow.name == name))


def load_board(session: Session, name: TBoardName) -> Board:
    return Board.model_validate_json(session.get_one(BoardRow, name).board)


def save_board(session: Session, name: TBoardName, board: Board) -> None:
    session.execute(update(BoardRow).where(BoardRow.name == name).values(board=board.model_dump_json()))


def load_draft(session: Session, name: TBoardName) -> Draft:
    return Draft.model_validate_json(session.get_one(BoardRow, name).draft)


def save_draft(session: Session, name: TBoardName, draft: Draft) -> None:
    session.execute(update(BoardRow).where(BoardRow.name == name).values(draft=draft.model_dump_json()))
