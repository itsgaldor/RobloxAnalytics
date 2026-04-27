"""
Schemas Pydantic para la configuración pública de una marca.
IMPORTANTE: Nunca incluir api_token ni universe_id en estos schemas.
"""
from pydantic import BaseModel


class BrandConfig(BaseModel):
    """
    Configuración pública de la marca.
    Privacidad by design: api_token y universe_id están explícitamente excluidos.
    """
    slug: str
    name: str
    logo_url: str | None
    banner_url: str | None
    primary_color: str


class BrandConfigResponse(BaseModel):
    """Respuesta estándar del endpoint de configuración."""
    data: BrandConfig
    meta: dict = {}
    error: str | None = None
