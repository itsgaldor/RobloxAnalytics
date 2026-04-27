"""
Schemas Pydantic para los eventos entrantes del Script de Roblox.
"""
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class EventType(str, Enum):
    join = "join"
    leave = "leave"
    heartbeat = "heartbeat"


class EventIn(BaseModel):
    """Payload que envía el Script de Roblox al endpoint de eventos."""
    event_type: EventType = Field(..., description="Tipo de evento: join, leave o heartbeat")
    session_id: str = Field(..., max_length=64, description="ID único de la sesión generado por el Script")
    user_id_hash: str = Field(..., max_length=64, description="SHA-256 del userId de Roblox")
    server_type: str = Field(..., pattern="^(public|private)$", description="Tipo de servidor: public o private")
    timestamp: datetime = Field(..., description="Timestamp del evento en el servidor de Roblox")


class EventResponse(BaseModel):
    """Respuesta estándar al procesar un evento."""
    data: dict
    meta: dict = {}
    error: str | None = None
