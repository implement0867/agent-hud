"""create boards and actions

Revision ID: 48c7179dfaa6
Revises:
Create Date: 2026-10-28 02:46:48.072575

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "48c7179dfaa6"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the boards, each with its checkpoint and the agent's position, and the actions on each board."""
    op.create_table(
        "boards",
        sa.Column("name", sa.Text(), primary_key=True),
        sa.Column("checkpoint_seq", sa.Integer(), nullable=False),
        sa.Column("checkpoint", sa.Text(), nullable=False),
        sa.Column("agent_seq", sa.Integer(), nullable=False),
        sqlite_strict=True,
    )
    op.create_table(
        "actions",
        sa.Column("board", sa.Text(), sa.ForeignKey("boards.name", ondelete="CASCADE"), primary_key=True),
        sa.Column("seq", sa.Integer(), primary_key=True),
        sa.Column("action", sa.Text(), nullable=False),
        sqlite_strict=True,
    )


def downgrade() -> None:
    """Drop the actions and the boards."""
    op.drop_table("actions")
    op.drop_table("boards")
