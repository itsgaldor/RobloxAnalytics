"""
Configuración de la base de datos async con SQLAlchemy 2.0.
"""
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def create_engine_and_session(database_url: str):
    """Crea el engine async y la fábrica de sesiones.
    SQLite (usado en tests) no soporta pool_size ni max_overflow.
    """
    is_sqlite = database_url.startswith("sqlite")
    engine_kwargs = {"echo": False}
    if not is_sqlite:
        engine_kwargs.update({
            "pool_pre_ping": True,
            "pool_size": 10,
            "max_overflow": 20,
        })
    engine = create_async_engine(database_url, **engine_kwargs)
    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    return engine, session_factory


# Engine y sesión globales (se inicializan en main.py con la URL del entorno)
_engine = None
_session_factory = None


def get_engine():
    return _engine


def get_session_factory():
    return _session_factory


def init_db(database_url: str):
    """Inicializa el engine global con la URL de la base de datos."""
    global _engine, _session_factory
    _engine, _session_factory = create_engine_and_session(database_url)
    return _engine, _session_factory
