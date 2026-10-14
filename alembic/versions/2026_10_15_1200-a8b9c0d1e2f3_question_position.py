"""question position

Revision ID: a8b9c0d1e2f3
Revises: f7a8b9c0d1e2
Create Date: 2026-10-15 12:00:00

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a8b9c0d1e2f3"
down_revision: Union[str, None] = "f7a8b9c0d1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "test_question_association",
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
    )
    # Прежний порядок: по номеру записи.
    op.execute("UPDATE test_question_association SET position = id")


def downgrade() -> None:
    op.drop_column("test_question_association", "position")
