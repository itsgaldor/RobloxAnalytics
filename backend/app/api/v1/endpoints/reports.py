"""
Endpoint de generacion de reportes PDF.
POST /api/v1/admin/brands/{brand_slug}/report
"""
import io
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator
from sqlalchemy import and_, case, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_db
from app.models.models import Brand, Session as SessionModel
from app.services.ai_analysis import generate_analysis
from app.services.metrics import _as_date
from app.services.pdf_generator import generate_report_pdf

router = APIRouter()

VALID_KPIS = {"sessions", "dau", "mau", "avg_session_minutes", "total_hours"}


class ReportRequest(BaseModel):
    date_from: date
    date_to: date
    kpis: list[str] = ["sessions", "dau", "mau", "avg_session_minutes", "total_hours"]
    include_ai: bool = False
    language: str = "es"

    @field_validator("date_to")
    @classmethod
    def validate_dates(cls, v, info):
        d_from = info.data.get("date_from")
        if d_from and v < d_from:
            raise ValueError("date_to debe ser >= date_from")
        if d_from and (v - d_from).days > 90:
            raise ValueError("El rango maximo es 90 dias")
        return v

    @field_validator("kpis")
    @classmethod
    def validate_kpis(cls, v):
        invalid = set(v) - VALID_KPIS
        if invalid:
            raise ValueError(f"KPIs invalidos: {invalid}")
        if not v:
            raise ValueError("Debe seleccionar al menos un KPI")
        return v

    @field_validator("language")
    @classmethod
    def validate_language(cls, v):
        if v not in ("es", "en"):
            raise ValueError('language debe ser "es" o "en"')
        return v


async def _metrics_for_range(db: AsyncSession, brand_id, start: datetime, end: datetime) -> dict:
    """Calcula metricas agregadas para un rango de fechas arbitrario."""
    # Sesiones totales
    total = (await db.execute(
        select(func.count()).where(and_(
            SessionModel.brand_id == brand_id,
            SessionModel.joined_at >= start,
            SessionModel.joined_at <= end,
        ))
    )).scalar() or 0

    # DAU promedio
    dau_rows = (await db.execute(
        select(
            func.date(SessionModel.joined_at).label("day"),
            func.count(distinct(SessionModel.user_id_hash)).label("u"),
        ).where(and_(
            SessionModel.brand_id == brand_id,
            SessionModel.joined_at >= start,
            SessionModel.joined_at <= end,
        )).group_by(func.date(SessionModel.joined_at))
    )).all()
    avg_dau = (sum(r.u for r in dau_rows) / len(dau_rows)) if dau_rows else 0.0

    # MAU (ventana de 30 dias desde el fin del periodo)
    mau_start = (end - timedelta(days=29)).replace(hour=0, minute=0, second=0, microsecond=0)
    mau = (await db.execute(
        select(func.count(distinct(SessionModel.user_id_hash))).where(and_(
            SessionModel.brand_id == brand_id,
            SessionModel.joined_at >= mau_start,
            SessionModel.joined_at <= end,
        ))
    )).scalar() or 0

    # Tiempos
    tr = (await db.execute(
        select(
            func.avg(SessionModel.duration_seconds).label("avg_dur"),
            func.sum(SessionModel.duration_seconds).label("total_sec"),
        ).where(and_(
            SessionModel.brand_id == brand_id,
            SessionModel.joined_at >= start,
            SessionModel.joined_at <= end,
            SessionModel.left_at.is_not(None),
            SessionModel.duration_seconds.is_not(None),
        ))
    )).one()

    return {
        "sessions":            total,
        "dau":                 round(avg_dau, 2),
        "mau":                 mau,
        "avg_session_minutes": round((tr.avg_dur or 0) / 60, 2),
        "total_hours":         round((tr.total_sec or 0) / 3600, 2),
    }


async def _daily_for_range(db: AsyncSession, brand_id, start: datetime, end: datetime) -> list:
    """Devuelve datos diarios para un rango arbitrario, de mas reciente a mas antiguo."""
    rows = (await db.execute(
        select(
            func.date(SessionModel.joined_at).label("day"),
            func.count().label("sessions"),
            func.count(distinct(SessionModel.user_id_hash)).label("unique_users"),
            func.avg(case(
                (SessionModel.left_at.is_not(None), SessionModel.duration_seconds),
                else_=None,
            )).label("avg_duration"),
            func.sum(case(
                (SessionModel.left_at.is_not(None), SessionModel.duration_seconds),
                else_=0,
            )).label("total_seconds"),
            func.sum(case((SessionModel.server_type == "public",  1), else_=0)).label("pub"),
            func.sum(case((SessionModel.server_type == "private", 1), else_=0)).label("priv"),
        ).where(and_(
            SessionModel.brand_id == brand_id,
            SessionModel.joined_at >= start,
            SessionModel.joined_at <= end,
        )).group_by(func.date(SessionModel.joined_at))
        .order_by(func.date(SessionModel.joined_at).desc())
    )).all()

    by_day = {
        _as_date(r.day): {
            "date":            _as_date(r.day),
            "sessions":        r.sessions,
            "unique_users":    r.unique_users,
            "avg_minutes":     round((r.avg_duration or 0) / 60, 2),
            "total_hours":     round((r.total_seconds or 0) / 3600, 2),
            "public_sessions": r.pub,
            "private_sessions": r.priv,
        }
        for r in rows
    }

    # Rellenar todos los dias del rango
    all_days, current = [], end.date()
    while current >= start.date():
        all_days.append(by_day.get(current, {
            "date": current, "sessions": 0, "unique_users": 0,
            "avg_minutes": 0.0, "total_hours": 0.0,
            "public_sessions": 0, "private_sessions": 0,
        }))
        current -= timedelta(days=1)
    return all_days


@router.post("/admin/brands/{brand_slug}/report")
async def generate_report(
    brand_slug: str,
    body: ReportRequest,
    db: AsyncSession = Depends(get_db),
):
    """Genera y devuelve un reporte PDF de metricas para una marca."""
    # Buscar la marca
    brand = (await db.execute(
        select(Brand).where(Brand.slug == brand_slug)
    )).scalar_one_or_none()

    if not brand:
        raise HTTPException(
            status_code=404,
            detail={"data": None, "meta": {}, "error": f"Marca '{brand_slug}' no encontrada"},
        )

    # Rango actual
    start = datetime.combine(body.date_from, datetime.min.time()).replace(tzinfo=timezone.utc)
    end   = datetime.combine(body.date_to,   datetime.max.time()).replace(tzinfo=timezone.utc)

    # Rango anterior (mismo numero de dias, inmediatamente antes)
    days       = (body.date_to - body.date_from).days + 1
    prev_end   = start - timedelta(seconds=1)
    prev_start = prev_end.replace(
        hour=0, minute=0, second=0, microsecond=0
    ) - timedelta(days=days - 1)

    # Calcular metricas
    metrics      = await _metrics_for_range(db, brand.id, start, end)
    prev_metrics = await _metrics_for_range(db, brand.id, prev_start, prev_end)
    daily_data   = await _daily_for_range(db, brand.id, start, end)

    # Deltas para el analisis de IA
    def safe_delta(cur, prev):
        if not prev:
            return 0.0
        return ((cur - prev) / prev) * 100

    deltas = {k: safe_delta(metrics[k], prev_metrics[k]) for k in metrics}

    # Dia pico y dia mas bajo
    days_with = [d for d in daily_data if d["sessions"] > 0]
    if days_with:
        peak = max(days_with, key=lambda d: d["sessions"])
        low  = min(days_with, key=lambda d: d["sessions"])
        peak_day      = peak["date"].strftime("%d %b %Y")
        low_day       = low["date"].strftime("%d %b %Y")
        peak_sessions = peak["sessions"]
        low_sessions  = low["sessions"]
    else:
        peak_day = low_day = "—"
        peak_sessions = low_sessions = 0

    # Distribucion publico / privado
    total_pub  = sum(d["public_sessions"]  for d in daily_data)
    total_priv = sum(d["private_sessions"] for d in daily_data)
    total_all  = total_pub + total_priv or 1

    # Analisis de IA (opcional)
    ai_analysis = None
    used_mock   = False
    if body.include_ai:
        ai_data = {
            "brand_name":       brand.name,
            "period_label":     f"{body.date_from.strftime('%d %b %Y')} – {body.date_to.strftime('%d %b %Y')}",
            "prev_period_label": f"{prev_start.date().strftime('%d %b %Y')} – {prev_end.date().strftime('%d %b %Y')}",
            "metrics":          metrics,
            "deltas":           deltas,
            "peak_day":         peak_day,
            "peak_sessions":    peak_sessions,
            "low_day":          low_day,
            "low_sessions":     low_sessions,
            "pct_public":       (total_pub  / total_all) * 100,
            "pct_private":      (total_priv / total_all) * 100,
        }
        used_mock   = not bool(settings.anthropic_api_key)
        ai_analysis = await generate_analysis(ai_data, body.language)

    # Generar PDF
    pdf_bytes = generate_report_pdf(
        brand=brand,
        metrics=metrics,
        prev_metrics=prev_metrics,
        daily_data=daily_data,
        selected_kpis=body.kpis,
        ai_analysis=ai_analysis,
        used_mock_ai=used_mock,
        date_from=body.date_from,
        date_to=body.date_to,
        language=body.language,
    )

    filename = f"reporte_{brand_slug}_{body.date_from}_{body.date_to}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
