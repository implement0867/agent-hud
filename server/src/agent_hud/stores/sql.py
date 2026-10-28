from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import Engine, delete, select, update
from sqlalchemy.orm import Session

from agent_hud.boards import TBoardName
from agent_hud.models.state import BoardState
from agent_hud.tables import BoardRow


class SqlStore:
    """The state of each board in a row of the boards table, through a session that the caller commits."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def list_board_names(self) -> list[TBoardName]:
        return list(self.session.scalars(select(BoardRow.name)))

    def add_board(self, name: TBoardName) -> None:
        if self.session.get(BoardRow, name) is not None:
            raise ValueError(f"a board '{name}' exists")
        self.session.add(BoardRow(name=name))

    def remove_board(self, name: TBoardName) -> None:
        self.session.execute(delete(BoardRow).where(BoardRow.name == name))

    def load_board_state(self, name: TBoardName) -> BoardState:
        return self.session.get_one(BoardRow, name).state

    def save_board_state(self, name: TBoardName, state: BoardState) -> None:
        self.session.execute(update(BoardRow).where(BoardRow.name == name).values(state=state))

    def commit(self) -> None:
        self.session.commit()


@contextmanager
def open_sql_store(engine: Engine) -> Generator[SqlStore]:
    """Open a store on a new session, which rolls back what is not committed when it closes."""
    with Session(engine) as session:
        yield SqlStore(session)
