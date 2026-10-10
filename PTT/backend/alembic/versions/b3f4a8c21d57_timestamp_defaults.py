"""Use the SQL now() function for timestamp defaults instead of a frozen literal.

Revision ID: b3f4a8c21d57
Revises: 9c0d2a7e4b61
"""

from alembic import op
import sqlalchemy as sa


revision = "b3f4a8c21d57"
down_revision = "9c0d2a7e4b61"
branch_labels = None
depends_on = None

TIMESTAMP_COLUMNS = (
    ("alerts", "triggered_at"),
    ("audit_logs", "timestamp"),
    ("biometric_templates", "enrolled_at"),
    ("devices", "registered_at"),
    ("item_decommissions", "decommissioned_at"),
    ("items", "created_at"),
    ("items", "updated_at"),
    ("movements", "created_at"),
    ("reports", "generated_at"),
    ("rfid_events", "occurred_at"),
    ("users", "created_at"),
    ("users", "updated_at"),
    ("warehouse_requests", "created_at"),
)


def upgrade() -> None:
    for table, column in TIMESTAMP_COLUMNS:
        op.alter_column(table, column, server_default=sa.text("now()"))


def downgrade() -> None:
    # The previous defaults were a frozen timestamp literal; restoring it would reintroduce the defect.
    pass
