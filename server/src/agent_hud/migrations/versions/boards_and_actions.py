"""The boards, each with its checkpoint and the agent's position, and the actions on each board.

Revision ID: boards_and_actions
Revises:
Create Date: 2026-10-28

"""

import sqlalchemy as sa
from alembic import op

revision = "boards_and_actions"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
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
    op.drop_table("actions")
    op.drop_table("boards")
