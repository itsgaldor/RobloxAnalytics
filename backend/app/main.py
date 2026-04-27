"""
Punto de entrada de la aplicacion FastAPI.
Configura el lifespan, middlewares y registra todos los routers.
"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

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


# ── Resolucion del directorio frontend ────────────────────────────────────────
_frontend_candidates = [
    Path("/app/frontend"),
    Path(__file__).parent.parent / "frontend",
    Path(__file__).parent.parent.parent / "frontend",
]
_frontend_dir = next((p for p in _frontend_candidates if p.exists()), None)
_admin_dir = (_frontend_dir / "admin") if _frontend_dir else None


# ── Rutas explicitas del admin con verificacion de sesion ─────────────────────
# FastAPI routes tienen prioridad sobre StaticFiles mounts.
# Usamos rutas explicitas porque BaseHTTPMiddleware no intercepta
# de forma confiable los requests a sub-aplicaciones montadas.

def _check_admin_session(request: Request) -> bool:
    """Retorna True si la cookie de sesion es valida."""
    from app.api.v1.endpoints.auth import verify_session_token
    token = request.cookies.get("pca_admin_session", "")
    return verify_session_token(token)


@app.get("/admin", include_in_schema=False)
@app.get("/admin/", include_in_schema=False)
async def admin_root(request: Request):
    """Redirige a login si no hay sesion valida, sirve index.html si la hay."""
    if not _check_admin_session(request):
        return RedirectResponse(url="/admin/login.html", status_code=302)
    if _admin_dir and (_admin_dir / "index.html").exists():
        return FileResponse(str(_admin_dir / "index.html"))
    return RedirectResponse(url="/admin/login.html", status_code=302)


# ── Montaje de archivos estaticos ─────────────────────────────────────────────
if _frontend_dir:
    if _admin_dir and _admin_dir.exists():
        app.mount("/admin", StaticFiles(directory=str(_admin_dir), html=True), name="admin")
    app.mount("/dashboard", StaticFiles(directory=str(_frontend_dir), html=True), name="frontend")
