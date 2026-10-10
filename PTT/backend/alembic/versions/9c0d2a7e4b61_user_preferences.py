"""Add per-user report and alert preferences.

Revision ID: 9c0d2a7e4b61
Revises: e2b781af9c44
"""

from alembic import op
import sqlalchemy as sa


revision = "9c0d2a7e4b61"
down_revision = "e2b781af9c44"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_preferences",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("report_default_period", sa.String(length=10), nullable=False, server_default="week"),
        sa.Column("alert_status_filter", sa.String(length=20), nullable=False, server_default="all"),
        sa.Column("alert_type_filter", sa.String(length=40), nullable=False, server_default="all"),
        sa.CheckConstraint("report_default_period IN ('week', 'month')", name="ck_user_preferences_report_period"),
        sa.CheckConstraint("alert_status_filter IN ('all', 'activa', 'resuelta')", name="ck_user_preferences_alert_status"),
        sa.CheckConstraint(
            "alert_type_filter IN ('all', 'salida_no_autorizada', 'falla_dispositivo', 'manipulacion_sensor')",
            name="ck_user_preferences_alert_type",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )


def downgrade() -> None:
    op.drop_table("user_preferences")