"""
Servicio de metricas: calcula DAU, MAU, sesiones, tiempos y series temporales.
Toda la logica de negocio de metricas vive aqui, fuera de los endpoints.
Compatible con PostgreSQL (produccion) y SQLite (tests).
"""
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import and_, case, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Session as SessionModel
from app.schemas.metrics import DailyRow, ServerTypeMetrics, TimeSeriesPoint


def _as_date(value) -> date:
    """Convierte el resultado de func.date() a date, compatible con SQLite y PostgreSQL."""
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        return date.fromisoformat(value[:10])
    return value


def _get_date_range(range_type: str) -> tuple[datetime, datetime]:
    """Calcula el rango de fechas segun el tipo solicitado."""
    now = datetime.now(timezone.utc)
    today_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)

    if range_type == "day":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif range_type == "week":
        start = (now - timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0)
    elif range_type == "month":
        start = (now - timedelta(days=29)).replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        raise ValueError(f"Invalid range type: {range_type}")

    return start, today_end


def _get_mau_range() -> tuple[datetime, datetime]:
    """MAU siempre usa ventana de 30 dias independiente del range."""
    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=29)).replace(hour=0, minute=0, second=0, microsecond=0)
    end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
    return start, end


def _get_previous_range(range_type: str) -> tuple[datetime, datetime]:
    """
    Calcula el rango del periodo ANTERIOR del mismo tamaño.
    Usado para calcular la variacion % vs periodo anterior.
    - day   → ayer (hace 1 dia)
    - week  → semana pasada (hace 7-14 dias)
    - month → mes pasado (hace 30-60 dias)
    """
    now = datetime.now(timezone.utc)

    if range_type == "day":
        yesterday = now - timedelta(days=1)
        start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        end = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
    elif range_type == "week":
        start = (now - timedelta(days=13)).replace(hour=0, minute=0, second=0, microsecond=0)
        end = (now - timedelta(days=7)).replace(hour=23, minute=59, second=59, microsecond=999999)
    elif range_type == "month":
        start = (now - timedelta(days=59)).replace(hour=0, minute=0, second=0, microsecond=0)
        end = (now - timedelta(days=30)).replace(hour=23, minute=59, second=59, microsecond=999999)
    else:
        raise ValueError(f"Invalid range type: {range_type}")

    return start, end


async def get_combined_aggregate(
    db: AsyncSession,
    brand_id,
    start: datetime,
    end: datetime,
) -> dict:
    """
    Calcula metricas agregadas combinadas (public + private) para un rango
    de fechas arbitrario. Se usa para comparar con el periodo anterior.
    Retorna un dict plano con los totales combinados.
    """
    mau_start, mau_end = _get_mau_range()

    # Sesiones totales
    sessions_q = select(func.count()).where(
        and_(
            SessionModel.brand_id == brand_id,
            SessionModel.joined_at >= start,
            SessionModel.joined_at <= end,
        )
    )
    total_sessions = (await db.execute(sessions_q)).scalar() or 0

    # DAU promedio
    dau_q = (
        select(
            func.date(SessionModel.joined_at).label("day"),
            func.count(distinct(SessionModel.user_id_hash)).label("unique_users"),
        )
        .where(and_(
            SessionModel.brand_id == brand_id,
            SessionModel.joined_at >= start,
            SessionModel.joined_at <= end,
        ))
        .group_by(func.date(SessionModel.joined_at))
    )
    dau_rows = (await db.execute(dau_q)).all()
    avg_dau = (sum(r.unique_users for r in dau_rows) / len(dau_rows)) if dau_rows else 0.0

    # MAU (ventana fija de 30 dias)
    mau_q = select(func.count(distinct(SessionModel.user_id_hash))).where(
        and_(
            SessionModel.brand_id == brand_id,
            SessionModel.joined_at >= mau_start,
            SessionModel.joined_at <= mau_end,
        )
    )
    mau = (await db.execute(mau_q)).scalar() or 0

    # Tiempos
    time_q = select(
        func.avg(SessionModel.duration_seconds).label("avg_dur"),
        func.sum(SessionModel.duration_seconds).label("total_sec"),
    ).where(and_(
        SessionModel.brand_id == brand_id,
        SessionModel.joined_at >= start,
        SessionModel.joined_at <= end,
        SessionModel.left_at.is_not(None),
        SessionModel.duration_seconds.is_not(None),
    ))
    time_row = (await db.execute(time_q)).one()

    return {
        "sessions": total_sessions,
        "dau": round(avg_dau, 2),
        "mau": mau,
        "avg_session_minutes": round((time_row.avg_dur or 0) / 60, 2),
        "total_hours": round((time_row.total_sec or 0) / 3600, 2),
    }


async def get_metrics_by_server_type(
    db: AsyncSession,
    brand_id,
    range_type: str,
) -> dict[str, ServerTypeMetrics]:
    """
    Calcula todas las metricas del dashboard separadas por server_type.
    Solo considera sesiones con left_at NOT NULL para calculos de tiempo.
    """
    start, end = _get_date_range(range_type)
    mau_start, mau_end = _get_mau_range()

    results = {}

    for server_type in ("public", "private"):
        # --- Total sesiones en el rango ---
        total_sessions_q = select(func.count()).where(
            and_(
                SessionModel.brand_id == brand_id,
                SessionModel.server_type == server_type,
                SessionModel.joined_at >= start,
                SessionModel.joined_at <= end,
            )
        )
        total_result = await db.execute(total_sessions_q)
        total_sessions = total_result.scalar() or 0

        # --- DAU: usuarios unicos por dia, luego promedio ---
        dau_q = (
            select(
                func.date(SessionModel.joined_at).label("day"),
                func.count(distinct(SessionModel.user_id_hash)).label("unique_users"),
            )
            .where(
                and_(
                    SessionModel.brand_id == brand_id,
                    SessionModel.server_type == server_type,
                    SessionModel.joined_at >= start,
                    SessionModel.joined_at <= end,
                )
            )
            .group_by(func.date(SessionModel.joined_at))
        )
        dau_result = await db.execute(dau_q)
        dau_rows = dau_result.all()
        avg_dau = (
            sum(row.unique_users for row in dau_rows) / len(dau_rows)
            if dau_rows else 0.0
        )

        # --- MAU: usuarios unicos en los ultimos 30 dias (siempre) ---
        mau_q = select(func.count(distinct(SessionModel.user_id_hash))).where(
            and_(
                SessionModel.brand_id == brand_id,
                SessionModel.server_type == server_type,
                SessionModel.joined_at >= mau_start,
                SessionModel.joined_at <= mau_end,
            )
        )
        mau_result = await db.execute(mau_q)
        mau = mau_result.scalar() or 0

        # --- Promedios de tiempo (solo sesiones completadas con left_at NOT NULL) ---
        time_q = select(
            func.avg(SessionModel.duration_seconds).label("avg_dur"),
            func.sum(SessionModel.duration_seconds).label("total_sec"),
        ).where(
            and_(
                SessionModel.brand_id == brand_id,
                SessionModel.server_type == server_type,
                SessionModel.joined_at >= start,
                SessionModel.joined_at <= end,
                SessionModel.left_at.is_not(None),
                SessionModel.duration_seconds.is_not(None),
            )
        )
        time_result = await db.execute(time_q)
        time_row = time_result.one()
        avg_session_minutes = ((time_row.avg_dur or 0) / 60)
        total_hours = ((time_row.total_sec or 0) / 3600)

        # --- Time series: metricas por dia ---
        time_series = await _build_time_series(db, brand_id, server_type, start, end)

        results[server_type] = ServerTypeMetrics(
            sessions=total_sessions,
            dau=round(avg_dau, 2),
            mau=mau,
            avg_session_minutes=round(avg_session_minutes, 2),
            total_hours=round(total_hours, 2),
            time_series=time_series,
        )

    return results


async def _build_time_series(
    db: AsyncSession,
    brand_id,
    server_type: str,
    start: datetime,
    end: datetime,
) -> list[TimeSeriesPoint]:
    """
    Construye la serie temporal dia a dia para un tipo de servidor.
    Garantiza que todos los dias del rango esten presentes, incluso con 0.
    """
    # Sesiones totales por dia
    sessions_q = (
        select(
            func.date(SessionModel.joined_at).label("day"),
            func.count().label("sessions"),
        )
        .where(
            and_(
                SessionModel.brand_id == brand_id,
                SessionModel.server_type == server_type,
                SessionModel.joined_at >= start,
                SessionModel.joined_at <= end,
            )
        )
        .group_by(func.date(SessionModel.joined_at))
    )
    sessions_result = await db.execute(sessions_q)
    sessions_by_day = {_as_date(row.day): row.sessions for row in sessions_result.all()}

    # Usuarios unicos por dia
    dau_q = (
        select(
            func.date(SessionModel.joined_at).label("day"),
            func.count(distinct(SessionModel.user_id_hash)).label("unique_users"),
        )
        .where(
            and_(
                SessionModel.brand_id == brand_id,
                SessionModel.server_type == server_type,
                SessionModel.joined_at >= start,
                SessionModel.joined_at <= end,
            )
        )
        .group_by(func.date(SessionModel.joined_at))
    )
    dau_result = await db.execute(dau_q)
    dau_by_day = {_as_date(row.day): row.unique_users for row in dau_result.all()}

    # Promedio de duracion por dia (solo sesiones completadas)
    avg_q = (
        select(
            func.date(SessionModel.joined_at).label("day"),
            func.avg(SessionModel.duration_seconds).label("avg_duration"),
        )
        .where(
            and_(
                SessionModel.brand_id == brand_id,
                SessionModel.server_type == server_type,
                SessionModel.joined_at >= start,
                SessionModel.joined_at <= end,
                SessionModel.left_at.is_not(None),
            )
        )
        .group_by(func.date(SessionModel.joined_at))
    )
    avg_result = await db.execute(avg_q)
    avg_by_day = {_as_date(row.day): (row.avg_duration or 0) for row in avg_result.all()}

    # Generar todos los dias del rango
    points = []
    current = start.date()
    end_date = end.date()

    while current <= end_date:
        points.append(
            TimeSeriesPoint(
                date=current,
                sessions=sessions_by_day.get(current, 0),
                dau=dau_by_day.get(current, 0),
                avg_minutes=round(avg_by_day.get(current, 0) / 60, 2),
            )
        )
        current += timedelta(days=1)

    return points


async def get_daily_metrics(
    db: AsyncSession,
    brand_id,
    range_type: str,
) -> list[DailyRow]:
    """
    Devuelve metricas diarias combinadas (public + private) ordenadas por fecha desc.
    """
    start, end = _get_date_range(range_type)

    q = (
        select(
            func.date(SessionModel.joined_at).label("day"),
            func.count().label("sessions"),
            func.count(distinct(SessionModel.user_id_hash)).label("unique_users"),
            func.avg(
                case(
                    (SessionModel.left_at.is_not(None), SessionModel.duration_seconds),
                    else_=None,
                )
            ).label("avg_duration"),
            func.sum(
                case(
                    (SessionModel.left_at.is_not(None), SessionModel.duration_seconds),
                    else_=0,
                )
            ).label("total_seconds"),
            func.sum(
                case((SessionModel.server_type == "public", 1), else_=0)
            ).label("public_sessions"),
            func.sum(
                case((SessionModel.server_type == "private", 1), else_=0)
            ).label("private_sessions"),
        )
        .where(
            and_(
                SessionModel.brand_id == brand_id,
                SessionModel.joined_at >= start,
                SessionModel.joined_at <= end,
            )
        )
        .group_by(func.date(SessionModel.joined_at))
        .order_by(func.date(SessionModel.joined_at).desc())
    )

    result = await db.execute(q)
    rows = result.all()

    daily_rows = {
        _as_date(row.day): DailyRow(
            date=_as_date(row.day),
            sessions=row.sessions,
            unique_users=row.unique_users,
            avg_minutes=round((row.avg_duration or 0) / 60, 2),
            total_hours=round((row.total_seconds or 0) / 3600, 2),
            public_sessions=row.public_sessions,
            private_sessions=row.private_sessions,
        )
        for row in rows
    }

    # Garantizar todos los dias del rango
    all_days = []
    current = end.date()
    stop = start.date()
    while current >= stop:
        if current in daily_rows:
            all_days.append(daily_rows[current])
        else:
            all_days.append(DailyRow(
                date=current,
                sessions=0,
                unique_users=0,
                avg_minutes=0.0,
                total_hours=0.0,
                public_sessions=0,
                private_sessions=0,
            ))
        current -= timedelta(days=1)

    return all_days
