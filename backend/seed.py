"""
Script de seed: genera 30 días de data falsa para Yape y Demo.
Idempotente: borra y recrea la data en cada ejecución.
Ejecutar con: python seed.py
"""
import asyncio
import hashlib
import os
import random
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Cargar .env si está disponible
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://pca:pca@localhost:5432/pca",
)


# ---------------------------------------------------------------------------
# Configuración de marcas
# ---------------------------------------------------------------------------
BRANDS = [
    {
        "slug": "yape",
        "name": "Yape",
        "primary_color": "#6C3ADE",
        "logo_url": "https://placehold.co/200x80?text=Yape",
        "banner_url": "https://placehold.co/1200x300/6C3ADE/white?text=Yape+en+Roblox",
        "universe_id": "1234567890",
        # Parámetros de generación de sesiones
        "weekend_range": (800, 1400),
        "weekday_range": (500, 900),
        "public_ratio": 0.70,
        "duration_mean": 1320,   # ~22 min
        "duration_std": 480,
        "unique_user_ratio": 0.60,  # 60% del total de sesiones son usuarios únicos por día
    },
    {
        "slug": "demo",
        "name": "Marca Demo",
        "primary_color": "#0F7AFF",
        "logo_url": "https://placehold.co/200x80?text=Demo",
        "banner_url": "https://placehold.co/1200x300/0F7AFF/white?text=Marca+Demo+en+Roblox",
        "universe_id": "9876543210",
        "weekend_range": (200, 500),
        "weekday_range": (100, 300),
        "public_ratio": 0.90,
        "duration_mean": 840,    # ~14 min
        "duration_std": 300,
        "unique_user_ratio": 0.70,
    },
]


def generate_duration(mean: int, std: int) -> int:
    """Genera una duración en segundos con distribución normal. Mínimo 30 segundos."""
    duration = int(random.gauss(mean, std))
    return max(30, duration)


def generate_session_id() -> str:
    """Genera un ID de sesión único."""
    return uuid.uuid4().hex


def generate_user_id_hash(user_pool: list[str]) -> str:
    """Selecciona un usuario del pool y devuelve su hash SHA-256."""
    user_id = random.choice(user_pool)
    return hashlib.sha256(user_id.encode()).hexdigest()


def generate_joined_at(day: datetime) -> datetime:
    """Genera un timestamp aleatorio dentro del día dado."""
    # Distribuir sesiones a lo largo del día con pico en tarde/noche (horario Perú)
    hour = random.choices(
        range(24),
        weights=[
            1, 1, 1, 1, 1, 1,    # 00-05: madrugada (bajo)
            2, 3, 4, 4, 4, 4,    # 06-11: mañana (medio)
            5, 5, 5, 6, 7, 8,    # 12-17: tarde (alto)
            9, 9, 8, 7, 5, 3,    # 18-23: noche (pico Roblox)
        ],
        k=1,
    )[0]
    minute = random.randint(0, 59)
    second = random.randint(0, 59)
    return day.replace(hour=hour, minute=minute, second=second, microsecond=0)


async def seed_brand(
    session: AsyncSession,
    brand_config: dict,
    today: datetime,
) -> tuple[str, int]:
    """Crea o actualiza una marca y genera 30 días de sesiones."""
    from app.models.models import Brand, Session as SessionModel

    # Idempotencia: borrar sesiones existentes de esta marca primero
    existing_brand = await session.execute(
        text("SELECT id FROM brands WHERE slug = :slug"),
        {"slug": brand_config["slug"]},
    )
    existing_row = existing_brand.fetchone()

    if existing_row:
        brand_id = existing_row[0]
        await session.execute(
            text("DELETE FROM sessions WHERE brand_id = :brand_id"),
            {"brand_id": brand_id},
        )
        await session.execute(
            text("DELETE FROM brands WHERE id = :brand_id"),
            {"brand_id": brand_id},
        )
        await session.commit()

    # Crear la marca con token único
    api_token = str(uuid.uuid4()).replace("-", "")
    brand = Brand(
        slug=brand_config["slug"],
        name=brand_config["name"],
        primary_color=brand_config["primary_color"],
        logo_url=brand_config["logo_url"],
        banner_url=brand_config["banner_url"],
        universe_id=brand_config["universe_id"],
        api_token=api_token,
    )
    session.add(brand)
    await session.flush()  # Para obtener el brand.id

    # Pool de usuarios virtuales (~3x el máximo de sesiones diarias para simular recurrencia)
    max_sessions = brand_config["weekend_range"][1]
    pool_size = int(max_sessions / brand_config["unique_user_ratio"] * 1.5)
    user_pool = [f"roblox_user_{brand_config['slug']}_{i}" for i in range(pool_size)]

    total_sessions = 0
    sessions_batch = []

    for days_ago in range(29, -1, -1):
        day = (today - timedelta(days=days_ago)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        is_weekend = day.weekday() >= 5  # 5=sábado, 6=domingo

        if is_weekend:
            num_sessions = random.randint(*brand_config["weekend_range"])
        else:
            num_sessions = random.randint(*brand_config["weekday_range"])

        # Calcular pool de usuarios únicos para este día (~unique_user_ratio del total)
        num_unique = max(1, int(num_sessions * brand_config["unique_user_ratio"]))
        day_user_pool = random.sample(user_pool, min(num_unique, len(user_pool)))

        for _ in range(num_sessions):
            # Seleccionar usuario del pool del día (puede repetirse)
            user_hash = generate_user_id_hash(day_user_pool)
            server_type = "public" if random.random() < brand_config["public_ratio"] else "private"
            duration = generate_duration(brand_config["duration_mean"], brand_config["duration_std"])
            joined_at = generate_joined_at(day)
            left_at = joined_at + timedelta(seconds=duration)

            sessions_batch.append(SessionModel(
                brand_id=brand.id,
                session_id=generate_session_id(),
                user_id_hash=user_hash,
                server_type=server_type,
                joined_at=joined_at,
                left_at=left_at,
                last_heartbeat=left_at,
                duration_seconds=duration,
            ))
            total_sessions += 1

    # Insertar en lotes de 500 para eficiencia
    batch_size = 500
    for i in range(0, len(sessions_batch), batch_size):
        session.add_all(sessions_batch[i : i + batch_size])
        await session.flush()

    await session.commit()
    return brand_config["slug"], total_sessions


async def main():
    print("=" * 60)
    print("Peru City Analytics — Seed de data falsa")
    print("=" * 60)

    engine = create_async_engine(DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Importar Base y crear tablas si no existen
    from app.db.database import Base, init_db
    init_db(DATABASE_URL)

    async with engine.begin() as conn:
        # Importar modelos para que Base los conozca
        from app.models import models  # noqa
        await conn.run_sync(Base.metadata.create_all)

    today = datetime.now(timezone.utc)
    print(f"\nFecha base: {today.strftime('%Y-%m-%d')}")
    print(f"Generando 30 días de data para {len(BRANDS)} marcas...\n")

    async with session_factory() as session:
        for brand_config in BRANDS:
            slug, total = await seed_brand(session, brand_config, today)
            print(f"  ✓ {slug:10s} → {total:,} sesiones creadas")

    await engine.dispose()

    print("\n" + "=" * 60)
    print("Seed completado exitosamente.")
    print("Verificar en: http://localhost:8000/api/v1/yape/metrics?range=month")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
