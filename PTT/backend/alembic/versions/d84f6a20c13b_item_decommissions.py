"""Store item decommission history without deleting inventory rows.

Revision ID: d84f6a20c13b
Revises: c9416d23eab0
"""

from alembic import op
import sqlalchemy as sa


revision = "d84f6a20c13b"
down_revision = "c9416d23eab0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "item_decommissions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("decommissioned_by_user_id", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column("decommissioned_at", sa.DateTime(timezone=True), server_default="now()", nullable=False),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"]),
        sa.ForeignKeyConstraint(["decommissioned_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("item_id"),
    )


def downgrade() -> None:
    op.drop_table("item_decommissions")