"""Store item location and technical specifications.

Revision ID: c9416d23eab0
Revises: 7af12c8d9e30
"""

from alembic import op
import sqlalchemy as sa


revision = "c9416d23eab0"
down_revision = "7af12c8d9e30"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("items", sa.Column("location_id", sa.Integer(), nullable=True))
    op.add_column("items", sa.Column("specs", sa.JSON(), nullable=True))
    op.create_foreign_key("fk_items_location_id_locations", "items", "locations", ["location_id"], ["id"])


def downgrade() -> None:
    op.drop_constraint("fk_items_location_id_locations", "items", type_="foreignkey")
    op.drop_column("items", "specs")
    op.drop_column("items", "location_id")