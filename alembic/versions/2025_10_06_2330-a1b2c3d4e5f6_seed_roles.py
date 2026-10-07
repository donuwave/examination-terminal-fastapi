"""Seed roles

Revision ID: a1b2c3d4e5f6
Revises: 7490e76a3752
Create Date: 2025-10-06 23:30:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "7490e76a3752"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ROLES = ("Студент", "Преподаватель")


def upgrade() -> None:
    for name in ROLES:
        op.execute(
            f"INSERT INTO role (name) SELECT '{name}' "
            f"WHERE NOT EXISTS (SELECT 1 FROM role WHERE name = '{name}')"
        )


def downgrade() -> None:
    names = ", ".join(f"'{name}'" for name in ROLES)
    op.execute(f"DELETE FROM role WHERE name IN ({names})")
