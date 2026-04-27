"""
Fixtures de pytest para los tests de Peru City Analytics.
Usa SQLite async para tests (in-memory), sin necesidad de PostgreSQL.
"""
import hashlib
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.database import Base, init_db
from app.dependencies import get_db
from app.models.models import Brand, Session as SessionModel

# Base de datos SQLite en memoria para tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Crea el engine de test (SQLite in-memory) y las tablas."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="session")
async def test_session_factory(test_engine):
    """Crea la fábrica de sesiones para tests."""
    factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    return factory


@pytest_asyncio.fixture(scope="session")
async def seed_data(test_session_factory):
    """
    Crea data de test: 2 marcas con 30 días de sesiones cada una.
    Scope=session para no re-crear en cada test.
    """
    async with test_session_factory() as db:
        # Marca Yape
        yape = Brand(
            id=uuid.uuid4(),
            slug="yape",
            name="Yape",
            primary_color="#6C3ADE",
            logo_url="https://placehold.co/200x80?text=Yape",
            banner_url="https://placehold.co/1200x300/6C3ADE/white?text=Yape",
            universe_id="1234567890",
            api_token="yape-test-token-12345678901234567890123456789012",
        )
        # Marca Demo
        demo = Brand(
            id=uuid.uuid4(),
            slug="demo",
            name="Marca Demo",
            primary_color="#0F7AFF",
            logo_url="https://placehold.co/200x80?text=Demo",
            banner_url="https://placehold.co/1200x300/0F7AFF/white?text=Demo",
            universe_id="9876543210",
            api_token="demo-test-token-12345678901234567890123456789012",
        )
        db.add(yape)
        db.add(demo)
        await db.flush()

        # Generar 30 días de sesiones para Yape
        today = datetime.now(timezone.utc)
        sessions = []
        for days_ago in range(29, -1, -1):
            day = today - timedelta(days=days_ago)
            day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
            # 20 sesiones por día para Yape
            for i in range(20):
                user_hash = hashlib.sha256(f"yape_user_{i % 12}".encode()).hexdigest()
                server_type = "public" if i % 10 < 7 else "private"
                joined = day_start + timedelta(hours=10, minutes=i * 3)
                duration = 1200 + (i * 30)
                left = joined + timedelta(seconds=duration)
                sessions.append(SessionModel(
                    id=uuid.uuid4(),
                    brand_id=yape.id,
                    session_id=f"yape-sess-{days_ago}-{i}",
                    user_id_hash=user_hash,
                    server_type=server_type,
                    joined_at=joined,
                    left_at=left,
                    last_heartbeat=left,
                    duration_seconds=duration,
                ))

        # 10 sesiones por día para Demo
        for days_ago in range(29, -1, -1):
            day = today - timedelta(days=days_ago)
            day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
            for i in range(10):
                user_hash = hashlib.sha256(f"demo_user_{i % 7}".encode()).hexdigest()
                server_type = "public" if i % 10 < 9 else "private"
                joined = day_start + timedelta(hours=14, minutes=i * 5)
                duration = 840 + (i * 20)
                left = joined + timedelta(seconds=duration)
                sessions.append(SessionModel(
                    id=uuid.uuid4(),
                    brand_id=demo.id,
                    session_id=f"demo-sess-{days_ago}-{i}",
                    user_id_hash=user_hash,
                    server_type=server_type,
                    joined_at=joined,
                    left_at=left,
                    last_heartbeat=left,
                    duration_seconds=duration,
                ))

        db.add_all(sessions)
        await db.commit()

        return {"yape": yape, "demo": demo}


@pytest_asyncio.fixture(scope="session")
async def client(test_session_factory, seed_data):
    """
    Cliente HTTP de test con override de la dependencia get_db.
    """
    from app.main import app
    from app.db.database import init_db

    # Override de la DB para usar SQLite de test
    async def override_get_db():
        async with test_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    # Inicializar con URL de test para que lifespan no falle
    init_db(TEST_DATABASE_URL)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
def yape_token(seed_data):
    return seed_data["yape"].api_token


@pytest.fixture
def demo_token(seed_data):
    return seed_data["demo"].api_token
