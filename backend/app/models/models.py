"""
Modelos SQLAlchemy 2.0 para Peru City Analytics.
Define las tablas: brands y sessions.
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Brand(Base):
    """Marca cliente del SaaS con configuracion visual y token de API."""
    __tablename__ = "brands"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True,
        server_default=func.gen_random_uuid(), default=uuid.uuid4,
    )
    slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    banner_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    primary_color: Mapped[str] = mapped_column(String(7), nullable=False, default="#000000")
    universe_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    api_token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=datetime.utcnow,
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_event_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    sessions: Mapped[list["Session"]] = relationship(
        "Session", back_populates="brand", cascade="all, delete-orphan"
    )


class Session(Base):
    """Sesion de un usuario en la experiencia Roblox. user_id_hash garantiza privacidad."""
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True,
        server_default=func.gen_random_uuid(), default=uuid.uuid4,
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), nullable=False,
    )
    session_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    user_id_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    server_type: Mapped[str] = mapped_column(String(10), nullable=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_heartbeat: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    brand: Mapped["Brand"] = relationship("Brand", back_populates="sessions")

    __table_args__ = (
        Index("ix_sessions_brand_joined", "brand_id", "joined_at"),
        Index("ix_sessions_brand_user_joined", "brand_id", "user_id_hash", "joined_at"),
        Index("ix_sessions_heartbeat_active", "last_heartbeat",
              postgresql_where="left_at IS NULL"),
    )
