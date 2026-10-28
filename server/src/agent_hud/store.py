from typing import Protocol

from sqlalchemy import Engine, delete, select, update
from sqlalchemy.orm import Session

from agent_hud.models.actions import Action
from agent_hud.models.board import Board
from agent_hud.tables import ActionRow, BoardRow


class Store(Protocol):
    """
    The state of one board: the board at a checkpoint, the actions from there on, each at its sequence number, and
    the sequence number up to which an agent has had the actions.
    """

    def load(self) -> tuple[int, Board, list[Action], int]:
        """
        The checkpoint's sequence number and board, the actions from there on, and the agent's sequence number.
        ValidationError when the store holds a board or an action that this version does not take.
        """
        ...

    def append(self, seq: int, actions: list[Action]) -> None:
        """Keep the actions, the first at the sequence number."""
        ...

    def compact(self, seq: int, board: Board, read: int) -> None:
        """Make the board, which the actions before the sequence number made, the checkpoint; drop those actions; keep the agent's sequence number."""
        ...

    def keep_read(self, read: int) -> None:
        """Keep the sequence number up to which an agent has had the actions."""
        ...


class SqlStore:
    """The state of the board with the name, in its row of the boards table and its rows of the actions table."""

    def __init__(self, engine: Engine, name: str) -> None:
        self.engine = engine
        self.name = name

    def load(self) -> tuple[int, Board, list[Action], int]:
        with Session(self.engine) as session:
            board = session.get_one(BoardRow, self.name)
            actions = session.scalars(
                select(ActionRow.action)
                .where(ActionRow.board == self.name, ActionRow.seq >= board.checkpoint_seq)
                .order_by(ActionRow.seq)
            ).all()
            return board.checkpoint_seq, board.checkpoint, list(actions), board.agent_seq

    def append(self, seq: int, actions: list[Action]) -> None:
        with Session(self.engine) as session, session.begin():
            session.add_all(ActionRow(board=self.name, seq=seq + n, action=action) for n, action in enumerate(actions))

    def compact(self, seq: int, board: Board, read: int) -> None:
        with Session(self.engine) as session, session.begin():
            session.execute(
                update(BoardRow)
                .where(BoardRow.name == self.name)
                .values(checkpoint_seq=seq, checkpoint=board, agent_seq=read)
            )
            session.execute(delete(ActionRow).where(ActionRow.board == self.name, ActionRow.seq < seq))

    def keep_read(self, read: int) -> None:
        with Session(self.engine) as session, session.begin():
            session.execute(update(BoardRow).where(BoardRow.name == self.name).values(agent_seq=read))
