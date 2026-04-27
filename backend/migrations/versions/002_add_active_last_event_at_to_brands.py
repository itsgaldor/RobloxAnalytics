"""add_active_last_event_at_to_brands

Revision ID: 002_add_active_last_event_at
Revises: 001_initial
Create Date: 2026-04-25 00:00:00.000000

Agrega los campos:
  - active: bool — soft delete de marcas
  - last_event_at: datetime — último evento recibido (para health status)
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "002_add_active_last_event_at"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Agregar columna active con valor por defecto TRUE
    op.add_column(
        "brands",
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    # Agregar columna last_event_at (nullable — NULL = nunca recibió eventos)
    op.add_column(
        "brands",
        sa.Column("last_event_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("brands", "last_event_at")
    op.drop_column("brands", "active")
