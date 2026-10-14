"""question kinds

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-10-15 10:00:00

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "f7a8b9c0d1e2"
down_revision: Union[str, None] = "e6f7a8b9c0d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("question", sa.Column("kind", sa.String(), nullable=False, server_default="single"))
    op.add_column(
        "question",
        sa.Column("correct_answers", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
    )
    op.execute("UPDATE question SET correct_answers = ARRAY[correct_answer]")

    op.add_column(
        "test_progress_result", sa.Column("kind", sa.String(), nullable=False, server_default="single")
    )
    op.add_column(
        "test_progress_result",
        sa.Column("correct_answers", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
    )
    op.add_column(
        "test_progress_result",
        sa.Column("student_answers", postgresql.ARRAY(sa.String()), nullable=True),
    )
    op.execute("UPDATE test_progress_result SET correct_answers = ARRAY[correct_answer]")


def downgrade() -> None:
    op.drop_column("test_progress_result", "student_answers")
    op.drop_column("test_progress_result", "correct_answers")
    op.drop_column("test_progress_result", "kind")
    op.drop_column("question", "correct_answers")
    op.drop_column("question", "kind")
