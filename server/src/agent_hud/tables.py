from sqlalchemy import ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """The tables, each STRICT, so that SQLite refuses a value of the wrong type."""


class BoardRow(Base):
    """A board: its name, the board as JSON, and the user's draft of the next turn as JSON."""

    __tablename__ = "boards"
    __table_args__ = ({"sqlite_strict": True},)

    name: Mapped[str] = mapped_column(Text, primary_key=True)
    board: Mapped[str] = mapped_column(Text)
    draft: Mapped[str] = mapped_column(Text)


class TurnRow(Base):
    """A turn that the user sent and that some open monitor has not had, in the order sent; the actions as JSON."""

    __tablename__ = "turns"
    __table_args__ = (UniqueConstraint("board", "id"), {"sqlite_strict": True})

    seq: Mapped[int] = mapped_column(Integer, primary_key=True)
    board: Mapped[str] = mapped_column(ForeignKey("boards.name", ondelete="CASCADE"))
    id: Mapped[str] = mapped_column(Text)
    actions: Mapped[str] = mapped_column(Text)


class CursorRow(Base):
    """The agent's read cursor on a board, as JSON."""

    __tablename__ = "agent_cursors"
    __table_args__ = ({"sqlite_strict": True},)

    board: Mapped[str] = mapped_column(ForeignKey("boards.name", ondelete="CASCADE"), primary_key=True)
    cursor: Mapped[str] = mapped_column(Text)
