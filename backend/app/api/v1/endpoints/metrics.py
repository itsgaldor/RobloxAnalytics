"""
Endpoints de métricas del dashboard:
- GET /api/v1/{brand_slug}/metrics?range=day|week|month[&compare=true]
- GET /api/v1/{brand_slug}/metrics/daily?range=week|month
- GET /api/v1/{brand_slug}/export.csv?range=day|week|month
- POST /api/v1/{brand_slug}/refresh
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_brand, get_db
from app.models.models import Brand
from app.schemas.metrics import (
    DailyMetricsResponse,
    DailyRangeType,
    MetricsData,
    MetricsResponse,
    PreviousMetrics,
    RangeType,
)
from app.services.export import generate_csv
from app.services.metrics import (
    _get_previous_range,
    get_combined_aggregate,
    get_daily_metrics,
    get_metrics_by_server_type,
)

router = APIRouter()


@router.get(
    "/{brand_slug}/metrics",
    response_model=MetricsResponse,
    summary="Métricas del dashboard",
    description=(
        "Devuelve DAU, MAU, sesiones, tiempos y series temporales separadas por server_type. "
        "Con compare=true incluye las métricas del período anterior para calcular variación %."
    ),
)
async def get_metrics(
    range: RangeType = Query("week", description="Rango temporal: day, week o month"),
    compare: bool = Query(False, description="Si true, incluye métricas del período anterior"),
    brand: Brand = Depends(get_brand),
    db: AsyncSession = Depends(get_db),
) -> MetricsResponse:
    # Métricas del período actual separadas por server_type
    metrics = await get_metrics_by_server_type(db, brand.id, range)

    # Métricas del período anterior (solo si se solicita)
    previous = None
    if compare:
        prev_start, prev_end = _get_previous_range(range)
        prev_data = await get_combined_aggregate(db, brand.id, prev_start, prev_end)
        previous = PreviousMetrics(**prev_data)

    return MetricsResponse(
        data=MetricsData(
            public=metrics["public"],
            private=metrics["private"],
            previous=previous,
        ),
        meta={"brand": brand.slug, "range": range, "compare": compare},
        error=None,
    )


@router.get(
    "/{brand_slug}/metrics/daily",
    response_model=DailyMetricsResponse,
    summary="Métricas diarias detalladas",
    description="Array de métricas por día con sesiones públicas y privadas.",
)
async def get_daily(
    range: DailyRangeType = Query("week", description="Rango temporal: week o month"),
    brand: Brand = Depends(get_brand),
    db: AsyncSession = Depends(get_db),
) -> DailyMetricsResponse:
    rows = await get_daily_metrics(db, brand.id, range)
    return DailyMetricsResponse(
        data=rows,
        meta={"brand": brand.slug, "range": range, "total_days": len(rows)},
        error=None,
    )


@router.get(
    "/{brand_slug}/export.csv",
    summary="Exportar métricas en CSV",
    description="Descarga un CSV con las métricas diarias del rango solicitado.",
)
async def export_csv(
    range: RangeType = Query("week", description="Rango temporal: day, week o month"),
    brand: Brand = Depends(get_brand),
    db: AsyncSession = Depends(get_db),
):
    content, filename = await generate_csv(db, brand.id, brand.slug, range)
    return StreamingResponse(
        iter([content]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post(
    "/{brand_slug}/refresh",
    summary="Refrescar caché de métricas",
    description="Placeholder para futura invalidación de caché.",
)
async def refresh_metrics(brand: Brand = Depends(get_brand)):
    return {
        "data": {"refreshed_at": datetime.now(timezone.utc).isoformat()},
        "meta": {"brand": brand.slug},
        "error": None,
    }
