"""Keep device request nonces to reject replayed signed events.

Revision ID: 7af12c8d9e30
Revises: 4dec58c66b21
"""

from alembic import op
import sqlalchemy as sa


revision = "7af12c8d9e30"
down_revision = "4dec58c66b21"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "device_request_nonces",
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("nonce", sa.String(length=32), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"]),
        sa.PrimaryKeyConstraint("device_id", "nonce"),
    )


def downgrade() -> None:
    op.drop_table("device_request_nonces")