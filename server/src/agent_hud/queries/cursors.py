from sqlalchemy import update
from sqlalchemy.orm import Session

from agent_hud.boards import TBoardName
from agent_hud.models.cursor import ReadCursor
from agent_hud.tables import CursorRow


def load_cursor(session: Session, name: TBoardName) -> ReadCursor:
    return ReadCursor.model_validate_json(session.get_one(CursorRow, name).cursor)


def save_cursor(session: Session, name: TBoardName, cursor: ReadCursor) -> None:
    session.execute(update(CursorRow).where(CursorRow.board == name).values(cursor=cursor.model_dump_json()))
