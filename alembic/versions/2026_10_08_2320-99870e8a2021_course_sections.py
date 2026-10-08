"""course sections

Revision ID: 99870e8a2021
Revises: 62b578b2dedd
Create Date: 2026-10-08 23:20:37.804004

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "99870e8a2021"
down_revision: Union[str, None] = "62b578b2dedd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "course_section",
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["course_id"], ["course.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_course_section_course_id"), "course_section", ["course_id"]
    )

    op.add_column("course_material", sa.Column("section_id", sa.Integer(), nullable=True))
    op.create_index(
        op.f("ix_course_material_section_id"), "course_material", ["section_id"]
    )
    op.create_foreign_key(
        "fk_course_material_section_id",
        "course_material",
        "course_section",
        ["section_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.add_column(
        "course_test_association", sa.Column("section_id", sa.Integer(), nullable=True)
    )
    op.create_index(
        op.f("ix_course_test_association_section_id"),
        "course_test_association",
        ["section_id"],
    )
    op.create_foreign_key(
        "fk_course_test_association_section_id",
        "course_test_association",
        "course_section",
        ["section_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Уже существующее содержимое курсов переносим в один «Основной раздел».
    op.execute(
        """
        INSERT INTO course_section (course_id, title, position)
        SELECT c.id, 'Основной раздел', 0
        FROM course c
        WHERE EXISTS (SELECT 1 FROM course_material m WHERE m.course_id = c.id)
           OR EXISTS (SELECT 1 FROM course_test_association a WHERE a.course_id = c.id)
        """
    )
    op.execute(
        "UPDATE course_material m SET section_id = s.id "
        "FROM course_section s WHERE s.course_id = m.course_id"
    )
    op.execute(
        "UPDATE course_test_association a SET section_id = s.id "
        "FROM course_section s WHERE s.course_id = a.course_id"
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_course_test_association_section_id",
        "course_test_association",
        type_="foreignkey",
    )
    op.drop_index(
        op.f("ix_course_test_association_section_id"),
        table_name="course_test_association",
    )
    op.drop_column("course_test_association", "section_id")

    op.drop_constraint(
        "fk_course_material_section_id", "course_material", type_="foreignkey"
    )
    op.drop_index(op.f("ix_course_material_section_id"), table_name="course_material")
    op.drop_column("course_material", "section_id")

    op.drop_index(op.f("ix_course_section_course_id"), table_name="course_section")
    op.drop_table("course_section")
