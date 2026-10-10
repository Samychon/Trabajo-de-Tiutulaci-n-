"""Add normalized rejection details to warehouse requests.

Revision ID: e2b781af9c44
Revises: d84f6a20c13b
"""

from alembic import op
import sqlalchemy as sa


revision = "e2b781af9c44"
down_revision = "d84f6a20c13b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("warehouse_requests", sa.Column("rejected_by_user_id", sa.Integer(), nullable=True))
    op.add_column("warehouse_requests", sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("warehouse_requests", sa.Column("rejection_reason", sa.String(length=500), nullable=True))
    op.create_foreign_key(
        "fk_warehouse_requests_rejected_by_user_id_users",
        "warehouse_requests",
        "users",
        ["rejected_by_user_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_warehouse_requests_rejected_by_user_id_users", "warehouse_requests", type_="foreignkey")
    op.drop_column("warehouse_requests", "rejection_reason")
    op.drop_column("warehouse_requests", "rejected_at")
    op.drop_column("warehouse_requests", "rejected_by_user_id")