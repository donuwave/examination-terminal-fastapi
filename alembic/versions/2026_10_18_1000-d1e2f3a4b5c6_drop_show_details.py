"""drop profile.show_details

Revision ID: d1e2f3a4b5c6
Revises: c0d1e2f3a4b5
Create Date: 2026-10-18 10:00:00

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, None] = "c0d1e2f3a4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("profile", "show_details")


def downgrade() -> None:
    op.add_column(
        "profile",
        sa.Column("show_details", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
