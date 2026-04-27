"""
Schemas Pydantic para la configuracion publica de una marca.
IMPORTANTE: Nunca incluir api_token ni universe_id en estos schemas.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class BrandConfig(BaseModel):
    """
    Configuracion publica de la marca.
    Privacidad by design: api_token y universe_id estan explicitamente excluidos.
    """
    slug: str
    name: str
    logo_url: Optional[str]
    banner_url: Optional[str]
    primary_color: str
    health: str = "offline"
    last_event_at: Optional[datetime] = None


class BrandConfigResponse(BaseModel):
    """Respuesta estandar del endpoint de configuracion."""
    data: BrandConfig
    meta: dict = {}
    error: Optional[str] = None
