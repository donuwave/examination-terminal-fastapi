"""material views

Revision ID: b9c0d1e2f3a4
Revises: a8b9c0d1e2f3
Create Date: 2026-10-15 15:00:00

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b9c0d1e2f3a4"
down_revision: Union[str, None] = "a8b9c0d1e2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "material_view",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("material_id", sa.Integer(), nullable=False),
        sa.Column("first_viewed_at", sa.DateTime(), nullable=False),
        sa.Column("last_viewed_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["course_id"], ["course.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["profile.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["material_id"], ["course_material.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("student_id", "material_id", name="uq_material_view"),
    )
    op.create_index("ix_material_view_course_id", "material_view", ["course_id"])
    op.create_index("ix_material_view_student_id", "material_view", ["student_id"])


def downgrade() -> None:
    op.drop_index("ix_material_view_student_id", table_name="material_view")
    op.drop_index("ix_material_view_course_id", table_name="material_view")
    op.drop_table("material_view")
