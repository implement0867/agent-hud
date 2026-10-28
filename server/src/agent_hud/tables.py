from pydantic import BaseModel
from sqlalchemy import Text, TypeDecorator
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from agent_hud.models.state import BoardState


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
    """A board: its name and its state."""

    __tablename__ = "boards"
    __table_args__ = ({"sqlite_strict": True},)

    name: Mapped[str] = mapped_column(Text, primary_key=True)
    state: Mapped[BoardState] = mapped_column(PydanticJson(BoardState), default=BoardState)
