"""
Endpoint GET /api/v1/{brand_slug}/config
Devuelve la configuración pública de la marca.
NUNCA expone api_token ni universe_id.
"""
from fastapi import APIRouter, Depends

from app.dependencies import get_brand
from app.models.models import Brand
from app.schemas.config import BrandConfig, BrandConfigResponse

router = APIRouter()


@router.get(
    "/{brand_slug}/config",
    response_model=BrandConfigResponse,
    summary="Configuración pública de la marca",
    description="Devuelve slug, nombre y URLs de branding. Nunca expone api_token ni universe_id.",
)
async def get_brand_config(
    brand: Brand = Depends(get_brand),
) -> BrandConfigResponse:
    """
    Privacidad by design: construimos el schema BrandConfig explícitamente
    para asegurarnos de que api_token y universe_id nunca aparezcan en el response.
    """
    return BrandConfigResponse(
        data=BrandConfig(
            slug=brand.slug,
            name=brand.name,
            logo_url=brand.logo_url,
            banner_url=brand.banner_url,
            primary_color=brand.primary_color,
        ),
        meta={},
        error=None,
    )
