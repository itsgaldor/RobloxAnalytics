"""Initial schema: brands and sessions tables

Revision ID: 001_initial
Revises:
Create Date: 2025-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers
revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Tabla de marcas
    op.create_table(
        "brands",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("slug", sa.String(50), unique=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("logo_url", sa.Text, nullable=True),
        sa.Column("banner_url", sa.Text, nullable=True),
        sa.Column("primary_color", sa.String(7), nullable=False, server_default="#000000"),
        sa.Column("universe_id", sa.String(50), nullable=True),
        sa.Column("api_token", sa.String(64), unique=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # Tabla de sesiones
    op.create_table(
        "sessions",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "brand_id",
            UUID(as_uuid=True),
            sa.ForeignKey("brands.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("session_id", sa.String(64), unique=True, nullable=False),
        sa.Column("user_id_hash", sa.String(64), nullable=False),
        sa.Column("server_type", sa.String(10), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("left_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_heartbeat", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_seconds", sa.Integer, nullable=True),
    )

    # Índices de rendimiento
    op.create_index(
        "ix_sessions_brand_joined",
        "sessions",
        ["brand_id", "joined_at"],
    )
    op.create_index(
        "ix_sessions_brand_user_joined",
        "sessions",
        ["brand_id", "user_id_hash", "joined_at"],
    )
    op.create_index(
        "ix_sessions_heartbeat_active",
        "sessions",
        ["last_heartbeat"],
        postgresql_where=sa.text("left_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_sessions_heartbeat_active", table_name="sessions")
    op.drop_index("ix_sessions_brand_user_joined", table_name="sessions")
    op.drop_index("ix_sessions_brand_joined", table_name="sessions")
    op.drop_table("sessions")
    op.drop_table("brands")
