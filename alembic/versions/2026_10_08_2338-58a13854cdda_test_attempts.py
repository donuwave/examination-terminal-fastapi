"""test attempts

Revision ID: 58a13854cdda
Revises: 99870e8a2021
Create Date: 2026-10-08 23:38:15.496555

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "58a13854cdda"
down_revision: Union[str, None] = "99870e8a2021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "test_extra_attempt",
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.Column("test_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("extra", sa.Integer(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["course_id"], ["course.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["profile.id"],
        ),
        sa.ForeignKeyConstraint(
            ["test_id"],
            ["test.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "course_id", "test_id", "student_id", name="uq_extra_attempt"
        ),
    )
    op.add_column(
        "test",
        sa.Column(
            "pass_percent", sa.Integer(), server_default="60", nullable=False
        ),
    )
    op.add_column(
        "test",
        sa.Column(
            "max_attempts", sa.Integer(), server_default="2", nullable=False
        ),
    )
    op.add_column(
        "test",
        sa.Column(
            "retry_delay_minutes",
            sa.Integer(),
            server_default="120",
            nullable=False,
        ),
    )
    op.add_column(
        "test_progress",
        sa.Column(
            "attempt_no", sa.Integer(), server_default="1", nullable=False
        ),
    )
    op.add_column(
        "test_progress",
        sa.Column("finished_at", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "test_progress", sa.Column("passed", sa.Boolean(), nullable=True)
    )

    # Прежняя схема создавала записи «доступ открыт» (1) и «просрочено» (4) без прохождения:
    # теперь попытка появляется только при старте теста, поэтому такие записи удаляем.
    op.execute(
        "DELETE FROM test_progress_result WHERE test_progress_id IN "
        "(SELECT id FROM test_progress WHERE status IN (1, 4))"
    )
    op.execute("DELETE FROM test_progress WHERE status IN (1, 4)")

    # У завершённых попыток вычисляем момент завершения и итог по порогу 60%.
    op.execute(
        """
        UPDATE test_progress tp SET
            finished_at = COALESCE(tp.attempt_date, 0),
            passed = (
                COALESCE(tp.count_current_answer, 0) * 100 >=
                60 * GREATEST((SELECT count(*) FROM test_progress_result r
                               WHERE r.test_progress_id = tp.id), 1)
            )
        WHERE tp.status = 3
        """
    )


def downgrade() -> None:
    op.drop_column("test_progress", "passed")
    op.drop_column("test_progress", "finished_at")
    op.drop_column("test_progress", "attempt_no")
    op.drop_column("test", "retry_delay_minutes")
    op.drop_column("test", "max_attempts")
    op.drop_column("test", "pass_percent")
    op.drop_table("test_extra_attempt")
