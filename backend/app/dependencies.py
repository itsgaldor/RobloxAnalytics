"""
Dependencias compartidas de FastAPI.
Centraliza la obtención de sesiones DB y validación de marcas.
"""
from typing import AsyncGenerator

from fastapi import Depends, Header, HTTPException, Path, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session_factory
from app.models.models import Brand


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependencia que provee una sesión de base de datos por request."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_brand(
    brand_slug: str = Path(..., description="Slug único de la marca"),
    db: AsyncSession = Depends(get_db),
) -> Brand:
    """
    Dependencia que obtiene la marca por slug.
    Devuelve 404 si no existe.
    """
    result = await db.execute(
        select(Brand).where(Brand.slug == brand_slug, Brand.active != False)
    )
    brand = result.scalar_one_or_none()
    if brand is None:
        raise HTTPException(
            status_code=404,
            detail={
                "data": None,
                "meta": {},
                "error": f"Brand '{brand_slug}' not found",
            },
        )
    return brand


async def get_brand_with_auth(
    brand_slug: str = Path(..., description="Slug único de la marca"),
    x_api_token: str = Header(..., description="Token de autenticación de la marca"),
    db: AsyncSession = Depends(get_db),
) -> Brand:
    """
    Dependencia que valida brand_slug + api_token.
    Devuelve 404 si el slug no existe, 401 si el token no corresponde.
    """
    result = await db.execute(
        select(Brand).where(Brand.slug == brand_slug, Brand.active != False)
    )
    brand = result.scalar_one_or_none()
    if brand is None:
        raise HTTPException(
            status_code=404,
            detail={
                "data": None,
                "meta": {},
                "error": f"Brand '{brand_slug}' not found",
            },
        )
    if brand.api_token != x_api_token:
        raise HTTPException(
            status_code=401,
            detail={
                "data": None,
                "meta": {},
                "error": "Invalid API token for this brand",
            },
        )
    return brand


def require_admin_auth(request: "Request"):
    """Dependency para proteger endpoints de admin via cookie de sesion."""
    from app.api.v1.endpoints.auth import verify_session_token
    token = request.cookies.get("pca_admin_session", "")
    if not verify_session_token(token):
        raise HTTPException(status_code=401, detail="No autorizado")