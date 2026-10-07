"""course categories

Revision ID: 62b578b2dedd
Revises: d0dcbcc6de72
Create Date: 2026-10-07 22:19:19.140231

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "62b578b2dedd"
down_revision: Union[str, None] = "d0dcbcc6de72"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


CATEGORIES = (
    "Программирование",
    "Математика",
    "Базы данных",
    "Веб-разработка",
    "Физика",
    "Иностранные языки",
    "Другое",
)


def upgrade() -> None:
    op.create_table(
        "course_category",
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.add_column(
        "course", sa.Column("category_id", sa.Integer(), nullable=True)
    )
    op.create_index(
        op.f("ix_course_category_id"), "course", ["category_id"], unique=False
    )
    op.create_foreign_key(
        "fk_course_category_id",
        "course",
        "course_category",
        ["category_id"],
        ["id"],
    )

    categories = sa.table("course_category", sa.column("name", sa.String))
    op.bulk_insert(
        categories,
        [{"name": name} for name in CATEGORIES],
    )


def downgrade() -> None:
    op.drop_constraint("fk_course_category_id", "course", type_="foreignkey")
    op.drop_index(op.f("ix_course_category_id"), table_name="course")
    op.drop_column("course", "category_id")
    op.drop_table("course_category")
