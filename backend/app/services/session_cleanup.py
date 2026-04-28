"""
Limpieza periódica de sesiones huérfanas.
Una sesión huérfana no recibió heartbeat en más de 5 minutos y su left_at es NULL.
Se llama desde el APScheduler cada 5 minutos.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Session as SessionModel


async def close_orphan_sessions(db: AsyncSession) -> int:
    """
    Cierra sesiones que no recibieron heartbeat en más de 5 minutos.
    Calcula la duración hasta el último heartbeat y asigna left_at.
    Retorna el número de sesiones cerradas.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)

    result = await db.execute(
        select(SessionModel)
        .where(SessionModel.left_at.is_(None))
        .where(SessionModel.last_heartbeat < cutoff)
    )
    orphan_list = result.scalars().all()

    for session in orphan_list:
        last_hb = session.last_heartbeat
        joined  = session.joined_at

        # Asegurar timezone-aware para comparar
        if last_hb and last_hb.tzinfo is None:
            last_hb = last_hb.replace(tzinfo=timezone.utc)
        if joined and joined.tzinfo is None:
            joined = joined.replace(tzinfo=timezone.utc)

        session.left_at = last_hb
        if last_hb and joined:
            duration = int((last_hb - joined).total_seconds())
            session.duration_seconds = max(0, duration)

    if orphan_list:
        await db.commit()
        print(f"[PCA] Cleanup: {len(orphan_list)} sesiones huérfanas cerradas")

    return len(orphan_list)
