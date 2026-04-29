"""
Endpoints de métricas del dashboard:
- GET /api/v1/{brand_slug}/metrics?range=day|week|month[&date_from=YYYY-MM-DD&date_to=YYYY-MM-DD][&compare=true]
- GET /api/v1/{brand_slug}/metrics/daily?range=week|month[&date_from=YYYY-MM-DD&date_to=YYYY-MM-DD]
- GET /api/v1/{brand_slug}/export.csv?range=day|week|month[&date_from=YYYY-MM-DD&date_to=YYYY-MM-DD]
- POST /api/v1/{brand_slug}/refresh
"""
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_brand, get_db
from app.models.models import Brand
from app.schemas.metrics import (
    DailyMetricsResponse,
    MetricsData,
    MetricsResponse,
    PreviousMetrics,
)
from app.services.export import generate_csv, generate_csv_by_range
from app.services.metrics import (
    _build_combined_time_series,
    _get_date_range,
    _get_previous_range,
    get_combined_aggregate,
    get_daily_metrics,
    get_daily_metrics_by_custom_range,
    get_metrics_by_custom_range,
    get_metrics_by_server_type,
)

router = APIRouter()


def _resolve_range(
    range_type: Optional[str],
    date_from: Optional[str],
    date_to: Optional[str],
) -> tuple[datetime, datetime]:
    """
    Resuelve el rango de fechas desde date_from/date_to o desde range_type.
    date_from y date_to tienen prioridad si ambos están presentes.
    """
    if date_from and date_to:
        try:
            start_date = date.fromisoformat(date_from)
            end_date = date.fromisoformat(date_to)
        except ValueError:
            raise HTTPException(400, detail="Formato de fecha inválido. Usa YYYY-MM-DD.")
        if start_date > end_date:
            raise HTTPException(400, detail="date_from debe ser anterior a date_to.")
        if (end_date - start_date).days > 90:
            raise HTTPException(400, detail="Rango máximo: 90 días.")
        start = datetime(start_date.year, start_date.month, start_date.day,
                         0, 0, 0, tzinfo=timezone.utc)
        end = datetime(end_date.year, end_date.month, end_date.day,
                       23, 59, 59, 999999, tzinfo=timezone.utc)
        return start, end

    rt = range_type or "week"
    if rt not in ("day", "week", "month"):
        raise HTTPException(400, detail="range debe ser day, week o month.")
    return _get_date_range(rt)


def _compute_previous_range(start: datetime, end: datetime) -> tuple[datetime, datetime]:
    """Calcula el período anterior del mismo número de días."""
    days = (end.date() - start.date()).days + 1
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=days - 1)
    prev_end_full = prev_end.replace(hour=23, minute=59, second=59, microsecond=999999)
    prev_start_full = prev_start.replace(hour=0, minute=0, second=0, microsecond=0)
    return prev_start_full, prev_end_full


@router.get(
    "/{brand_slug}/metrics",
    response_model=MetricsResponse,
    summary="Métricas del dashboard",
    description=(
        "Devuelve DAU, MAU, sesiones, tiempos y series temporales separadas por server_type. "
        "Acepta range=day|week|month o date_from/date_to (YYYY-MM-DD, máx 90 días). "
        "Con compare=true incluye las métricas del período anterior."
    ),
)
async def get_metrics(
    range: Optional[str] = Query("week", description="Rango temporal: day, week o month"),
    date_from: Optional[str] = Query(None, description="Fecha inicio YYYY-MM-DD (custom range)"),
    date_to: Optional[str] = Query(None, description="Fecha fin YYYY-MM-DD (custom range)"),
    compare: bool = Query(False, description="Si true, incluye métricas del período anterior"),
    brand: Brand = Depends(get_brand),
    db: AsyncSession = Depends(get_db),
) -> MetricsResponse:
    start, end = _resolve_range(range, date_from, date_to)
    is_custom = bool(date_from and date_to)

    # Métricas del período actual
    if is_custom:
        metrics = await get_metrics_by_custom_range(db, brand.id, start, end)
    else:
        metrics = await get_metrics_by_server_type(db, brand.id, range or "week")

    # Período anterior
    previous = None
    if compare:
        if is_custom:
            prev_start, prev_end = _compute_previous_range(start, end)
        else:
            prev_start, prev_end = _get_previous_range(range or "week")
        prev_data = await get_combined_aggregate(db, brand.id, prev_start, prev_end)
        prev_ts = await _build_combined_time_series(db, brand.id, prev_start, prev_end)
        previous = PreviousMetrics(**prev_data, time_series=prev_ts)

    return MetricsResponse(
        data=MetricsData(
            public=metrics["public"],
            private=metrics["private"],
            previous=previous,
        ),
        meta={
            "brand": brand.slug,
            "range": range,
            "date_from": date_from,
            "date_to": date_to,
            "compare": compare,
        },
        error=None,
    )


@router.get(
    "/{brand_slug}/metrics/daily",
    response_model=DailyMetricsResponse,
    summary="Métricas diarias detalladas",
    description="Array de métricas por día. Acepta range=week|month o date_from/date_to.",
)
async def get_daily(
    range: Optional[str] = Query("week", description="Rango temporal: week o month"),
    date_from: Optional[str] = Query(None, description="Fecha inicio YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="Fecha fin YYYY-MM-DD"),
    brand: Brand = Depends(get_brand),
    db: AsyncSession = Depends(get_db),
) -> DailyMetricsResponse:
    if date_from and date_to:
        start, end = _resolve_range(range, date_from, date_to)
        rows = await get_daily_metrics_by_custom_range(db, brand.id, start, end)
    else:
        rt = range if range in ("week", "month") else "week"
        rows = await get_daily_metrics(db, brand.id, rt)
    return DailyMetricsResponse(
        data=rows,
        meta={"brand": brand.slug, "range": range, "total_days": len(rows)},
        error=None,
    )


@router.get(
    "/{brand_slug}/export.csv",
    summary="Exportar métricas en CSV",
    description="Descarga un CSV con las métricas diarias. Acepta range o date_from/date_to.",
)
async def export_csv(
    range: Optional[str] = Query("week", description="Rango temporal: day, week o month"),
    date_from: Optional[str] = Query(None, description="Fecha inicio YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="Fecha fin YYYY-MM-DD"),
    brand: Brand = Depends(get_brand),
    db: AsyncSession = Depends(get_db),
):
    if date_from and date_to:
        start, end = _resolve_range(range, date_from, date_to)
        content, filename = await generate_csv_by_range(
            db, brand.id, brand.slug, start, end, date_from, date_to
        )
    else:
        content, filename = await generate_csv(db, brand.id, brand.slug, range or "week")
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
