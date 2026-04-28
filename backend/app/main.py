"""
Punto de entrada de la aplicacion FastAPI.
Configura el lifespan, middlewares y registra todos los routers.
"""
from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.v1.router import api_router
from app.config import settings
from app.db.database import Base, get_engine, get_session_factory, init_db
from app.limiter import limiter

# ── Scheduler global ──────────────────────────────────────────────────────────
_scheduler = AsyncIOScheduler()


async def _run_cleanup():
    """Wrapper que abre una sesión de DB y corre el cleanup de sesiones huérfanas."""
    from app.services.session_cleanup import close_orphan_sessions

    factory = get_session_factory()
    if factory is None:
        return
    async with factory() as db:
        await close_orphan_sessions(db)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestiona el ciclo de vida de la aplicacion: startup y shutdown."""
    # Inicializar DB
    engine, _ = init_db(settings.DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Iniciar scheduler de limpieza de sesiones
    _scheduler.add_job(_run_cleanup, "interval", minutes=5, id="session_cleanup")
    _scheduler.start()
    print("[PCA] Scheduler iniciado — limpieza de sesiones cada 5 min")

    yield

    # Shutdown
    _scheduler.shutdown(wait=False)
    await engine.dispose()


# ── Security Headers Middleware ───────────────────────────────────────────────

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Agrega headers de seguridad estándar a todas las respuestas."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        return response


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Dashboard SaaS multi-tenant de metricas de experiencias Roblox",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Security headers
app.add_middleware(SecurityHeadersMiddleware)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Exception handlers ────────────────────────────────────────────────────────

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Respuesta consistente para errores de validación Pydantic."""
    return JSONResponse(
        status_code=422,
        content={"data": None, "error": "Payload inválido", "meta": {}},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Manejador global de excepciones no controladas."""
    return JSONResponse(
        status_code=500,
        content={"data": None, "meta": {}, "error": "Internal server error"},
    )


# ── Routers ───────────────────────────────────────────────────────────────────

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
