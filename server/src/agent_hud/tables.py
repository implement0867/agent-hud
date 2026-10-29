from sqlalchemy import Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from agent_hud.models.state import BoardState


class Base(DeclarativeBase):
    """The tables, each STRICT, so that SQLite refuses a value of the wrong type."""


class BoardRow(Base):
    """A board: its name, and its state as JSON, which the queries parse."""

    __tablename__ = "boards"
    __table_args__ = ({"sqlite_strict": True},)

    name: Mapped[str] = mapped_column(Text, primary_key=True)
    state: Mapped[str] = mapped_column(Text, default=BoardState().model_dump_json())
