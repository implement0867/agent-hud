from pydantic import BaseModel
from sqlalchemy import ForeignKey, Integer, Text, TypeDecorator
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from agent_hud.models.actions import Action
from agent_hud.models.board import Board


class PydanticJson[T: BaseModel](TypeDecorator[T]):
    """A Pydantic model kept as its JSON text. ValidationError when a row holds JSON that the model does not take."""

    impl = Text
    cache_ok = True

    def __init__(self, model: type[T]) -> None:
        super().__init__()
        self.model = model

    def process_bind_param(self, value: T | None, dialect: Dialect) -> str | None:
        return None if value is None else value.model_dump_json()

    def process_result_value(self, value: str | None, dialect: Dialect) -> T | None:
        return None if value is None else self.model.model_validate_json(value)


class Base(DeclarativeBase):
    """The tables, each STRICT, so that SQLite refuses a value of the wrong type."""


class BoardRow(Base):
    """A board: its name, the board at its checkpoint, and the sequence number up to which an agent has had its actions."""

    __tablename__ = "boards"
    __table_args__ = ({"sqlite_strict": True},)

    name: Mapped[str] = mapped_column(Text, primary_key=True)
    checkpoint_seq: Mapped[int] = mapped_column(Integer, default=0)
    checkpoint: Mapped[Board] = mapped_column(PydanticJson(Board), default=Board)
    agent_seq: Mapped[int] = mapped_column(Integer, default=0)


class ActionRow(Base):
    """An action on a board, at its sequence number; deleting the board deletes its actions."""

    __tablename__ = "actions"
    __table_args__ = ({"sqlite_strict": True},)

    board: Mapped[str] = mapped_column(Text, ForeignKey(BoardRow.name, ondelete="CASCADE"), primary_key=True)
    seq: Mapped[int] = mapped_column(Integer, primary_key=True)
    action: Mapped[Action] = mapped_column(PydanticJson(Action))
