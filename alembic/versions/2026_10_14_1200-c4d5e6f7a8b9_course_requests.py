"""course requests

Revision ID: c4d5e6f7a8b9
Revises: 58a13854cdda
Create Date: 2026-10-14 12:00:00

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c4d5e6f7a8b9"
down_revision: Union[str, None] = "58a13854cdda"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "course",
        sa.Column("enrollment", sa.String(), nullable=False, server_default="open"),
    )
    op.create_table(
        "course_request",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["course_id"], ["course.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["profile.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_course_request_course_id", "course_request", ["course_id"])
    op.create_index("ix_course_request_student_id", "course_request", ["student_id"])
    op.create_index(
        "uq_course_request_pending",
        "course_request",
        ["course_id", "student_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_index("uq_course_request_pending", table_name="course_request")
    op.drop_index("ix_course_request_student_id", table_name="course_request")
    op.drop_index("ix_course_request_course_id", table_name="course_request")
    op.drop_table("course_request")
    op.drop_column("course", "enrollment")
