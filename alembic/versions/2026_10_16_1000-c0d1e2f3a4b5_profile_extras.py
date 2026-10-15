"""profile created_at, show_details, avatar; notification actor

Revision ID: c0d1e2f3a4b5
Revises: b9c0d1e2f3a4
Create Date: 2026-10-16 10:00:00

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c0d1e2f3a4b5"
down_revision: Union[str, None] = "b9c0d1e2f3a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "profile",
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )
    op.add_column(
        "profile",
        sa.Column("show_details", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column("profile", sa.Column("avatar", sa.String(), nullable=True))
    op.add_column("notification", sa.Column("actor_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_notification_actor_id_profile",
        "notification",
        "profile",
        ["actor_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_notification_actor_id_profile", "notification", type_="foreignkey")
    op.drop_column("notification", "actor_id")
    op.drop_column("profile", "avatar")
    op.drop_column("profile", "show_details")
    op.drop_column("profile", "created_at")
