"""
Endpoint GET /api/v1/{brand_slug}/config
Devuelve la configuracion publica de la marca.
NUNCA expone api_token ni universe_id.
"""
from fastapi import APIRouter, Depends

from app.api.v1.endpoints.admin import _compute_health
from app.dependencies import get_brand
from app.models.models import Brand
from app.schemas.config import BrandConfig, BrandConfigResponse

router = APIRouter()


@router.get(
    "/{brand_slug}/config",
    response_model=BrandConfigResponse,
    summary="Configuracion publica de la marca",
    description="Devuelve slug, nombre, URLs de branding, health y last_event_at. Nunca expone api_token ni universe_id.",
)
async def get_brand_config(
    brand: Brand = Depends(get_brand),
) -> BrandConfigResponse:
    """
    Privacidad by design: construimos el schema BrandConfig explicitamente
    para asegurarnos de que api_token y universe_id nunca aparezcan en el response.
    """
    return BrandConfigResponse(
        data=BrandConfig(
            slug=brand.slug,
            name=brand.name,
            logo_url=brand.logo_url,
            banner_url=brand.banner_url,
            primary_color=brand.primary_color,
            health=_compute_health(brand.last_event_at),
            last_event_at=brand.last_event_at,
        ),
        meta={},
        error=None,
    )
