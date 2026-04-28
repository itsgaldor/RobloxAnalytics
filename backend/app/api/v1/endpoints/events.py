"""
Endpoint POST /api/v1/{brand_slug}/events
Recibe eventos del Script de Roblox: join, leave, heartbeat.
Incluye rate limiting por IP (slowapi) y por api_token (DB).
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_brand_with_auth, get_db
from app.limiter import limiter
from app.models.models import Brand, Session as SessionModel
from app.schemas.events import EventIn, EventResponse, EventType

router = APIRouter()


async def _check_token_rate_limit(
    brand_id,
    db: AsyncSession,
    window_seconds: int = 60,
    max_events: int = 200,
) -> bool:
    """
    Verifica que la marca no exceda 200 eventos por minuto.
    Cuenta eventos (sesiones creadas) en la ventana de tiempo.
    Retorna True si está dentro del límite.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=window_seconds)
    result = await db.execute(
        select(func.count(SessionModel.id))
        .where(SessionModel.brand_id == brand_id)
        .where(SessionModel.joined_at >= cutoff)
    )
    count = result.scalar() or 0
    return count < max_events


@router.post(
    "/{brand_slug}/events",
    response_model=EventResponse,
    summary="Recibir evento de Roblox",
    description="Endpoint autenticado que recibe join, leave y heartbeat del Script de Roblox.",
)
@limiter.limit("120/minute")
async def receive_event(
    request: Request,
    event: EventIn,
    brand: Brand = Depends(get_brand_with_auth),
    db: AsyncSession = Depends(get_db),
) -> EventResponse:

    # Rate limit por api_token (cuenta eventos del brand en el último minuto)
    if not await _check_token_rate_limit(brand.id, db):
        raise HTTPException(
            status_code=429,
            detail={"data": None, "meta": {}, "error": "Rate limit excedido. Máximo 200 eventos por minuto por marca."},
        )

    # Convertir Unix timestamp (int) a datetime UTC
    timestamp = datetime.fromtimestamp(event.timestamp, tz=timezone.utc)

    if event.event_type == EventType.join:
        existing = await db.execute(
            select(SessionModel).where(SessionModel.session_id == event.session_id)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=409,
                detail={"data": None, "meta": {}, "error": f"Session '{event.session_id}' already exists"},
            )
        session = SessionModel(
            brand_id=brand.id,
            session_id=event.session_id,
            user_id_hash=event.user_id_hash,
            server_type=event.server_type,
            joined_at=timestamp,
            last_heartbeat=timestamp,
        )
        db.add(session)
        brand.last_event_at = datetime.now(timezone.utc)
        await db.commit()
        return EventResponse(
            data={"event": "join", "session_id": event.session_id},
            meta={}, error=None,
        )

    result = await db.execute(
        select(SessionModel).where(
            SessionModel.session_id == event.session_id,
            SessionModel.brand_id == brand.id,
        )
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(
            status_code=404,
            detail={"data": None, "meta": {}, "error": f"Session '{event.session_id}' not found for this brand"},
        )

    if event.event_type == EventType.heartbeat:
        session.last_heartbeat = timestamp
        brand.last_event_at = datetime.now(timezone.utc)
        await db.commit()
        return EventResponse(
            data={"event": "heartbeat", "session_id": event.session_id},
            meta={}, error=None,
        )

    if event.event_type == EventType.leave:
        session.left_at = timestamp
        session.last_heartbeat = timestamp
        joined_at = session.joined_at
        if joined_at.tzinfo is None:
            joined_at = joined_at.replace(tzinfo=timezone.utc)
        duration = int((timestamp - joined_at).total_seconds())
        session.duration_seconds = max(0, duration)
        brand.last_event_at = datetime.now(timezone.utc)
        await db.commit()
        return EventResponse(
            data={"event": "leave", "session_id": event.session_id, "duration_seconds": session.duration_seconds},
            meta={}, error=None,
        )
