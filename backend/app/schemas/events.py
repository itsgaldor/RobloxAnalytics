"""
Schemas Pydantic para los eventos entrantes del Script de Roblox.
Validación estricta para prevenir abuso y datos maliciosos.
"""
import re
import time
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class EventType(str, Enum):
    join = "join"
    leave = "leave"
    heartbeat = "heartbeat"


class EventIn(BaseModel):
    """Payload que envía el Script de Roblox al endpoint de eventos."""

    event_type: EventType = Field(..., description="Tipo de evento: join, leave o heartbeat")

    session_id: str = Field(
        ...,
        min_length=8,
        max_length=64,
        description="ID único de la sesión generado por el Script",
    )

    user_id_hash: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Hash deterministico del userId de Roblox",
    )

    server_type: str = Field(
        ...,
        pattern=r"^(public|private)$",
        description="Tipo de servidor: public o private",
    )

    timestamp: int = Field(
        ...,
        gt=0,
        lt=9_999_999_999,
        description="Unix timestamp del evento (segundos)",
    )

    @field_validator("session_id", "user_id_hash")
    @classmethod
    def no_special_chars(cls, v: str) -> str:
        """Solo alfanuméricos, guiones y guiones bajos — previene injection."""
        if not re.match(r"^[a-zA-Z0-9\-_]+$", v):
            raise ValueError("Caracteres no permitidos — solo alfanuméricos, - y _")
        return v

    @field_validator("timestamp")
    @classmethod
    def not_too_old(cls, v: int) -> int:
        """Rechazar eventos con timestamp de más de 5 minutos de diferencia."""
        if abs(time.time() - v) > 300:
            raise ValueError(
                "Timestamp fuera de rango — máximo 5 minutos de diferencia con el servidor"
            )
        return v

    model_config = {"extra": "ignore"}  # ignorar campos desconocidos silenciosamente


class EventResponse(BaseModel):
    """Respuesta estándar al procesar un evento."""

    data: dict
    meta: dict = {}
    error: str | None = None
