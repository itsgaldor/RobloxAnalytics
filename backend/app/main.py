"""
Punto de entrada de la aplicacion FastAPI.
Configura el lifespan, middlewares y registra todos los routers.
"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.v1.router import api_router
from app.config import settings
from app.db.database import Base, get_engine, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestiona el ciclo de vida de la aplicacion: startup y shutdown."""
    engine, _ = init_db(settings.DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Dashboard SaaS multi-tenant de metricas de experiencias Roblox",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AdminAuthMiddleware(BaseHTTPMiddleware):
    """
    Protege todas las rutas /admin/* excepto /admin/login.html y los
    endpoints de auth. Verifica la cookie de sesion en cada request.
    """
    EXEMPT_PATHS = [
        "/admin/login.html",
        "/api/v1/auth/",
        "/health",
    ]

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Solo proteger rutas /admin/
        if not path.startswith("/admin"):
            return await call_next(request)

        # Rutas exentas
        if any(path.startswith(p) for p in self.EXEMPT_PATHS):
            return await call_next(request)

        # Verificar sesion
        from app.api.v1.endpoints.auth import verify_session_token
        token = request.cookies.get("pca_admin_session", "")
        if not verify_session_token(token):
            return RedirectResponse(
                url=f"/admin/login.html?next={path}",
                status_code=302,
            )

        return await call_next(request)


app.add_middleware(AdminAuthMiddleware)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Manejador global de excepciones no controladas."""
    return JSONResponse(
        status_code=500,
        content={"data": None, "meta": {}, "error": "Internal server error"},
    )


app.include_router(api_router, prefix="/api/v1")


@app.get("/health", tags=["Health"])
async def health_check():
    """Endpoint de salud para el healthcheck de Docker y Railway."""
    return {"status": "ok", "version": settings.APP_VERSION, "environment": settings.ENVIRONMENT}


_frontend_candidates = [
    Path("/app/frontend"),
    Path(__file__).parent.parent / "frontend",
    Path(__file__).parent.parent.parent / "frontend",
]
_frontend_dir = next((p for p in _frontend_candidates if p.exists()), None)

if _frontend_dir:
    _admin_dir = _frontend_dir / "admin"
    if _admin_dir.exists():
        app.mount("/admin", StaticFiles(directory=str(_admin_dir), html=True), name="admin")
    app.mount("/dashboard", StaticFiles(directory=str(_frontend_dir), html=True), name="frontend")
