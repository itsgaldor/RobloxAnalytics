"""
Servicio de exportación de datos a CSV.
Genera el archivo CSV con las métricas diarias para una marca y rango.
"""
import csv
import io
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.metrics import get_daily_metrics


async def generate_csv(
    db: AsyncSession,
    brand_id,
    brand_slug: str,
    range_type: str,
) -> tuple[str, str]:
    """
    Genera el CSV de métricas diarias.
    Retorna (contenido_csv, nombre_archivo).
    """
    rows = await get_daily_metrics(db, brand_id, range_type)

    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "date",
            "sessions",
            "unique_users",
            "avg_session_minutes",
            "total_hours",
            "public_sessions",
            "private_sessions",
        ],
    )
    writer.writeheader()

    for row in rows:
        writer.writerow({
            "date": row.date.isoformat(),
            "sessions": row.sessions,
            "unique_users": row.unique_users,
            "avg_session_minutes": row.avg_minutes,
            "total_hours": row.total_hours,
            "public_sessions": row.public_sessions,
            "private_sessions": row.private_sessions,
        })

    today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    filename = f"{brand_slug}_{range_type}_{today_str}.csv"

    return output.getvalue(), filename
