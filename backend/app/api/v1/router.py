"""
Router principal de la API v1.
Agrega todos los routers de endpoints en un solo lugar.
"""
from fastapi import APIRouter

from app.api.v1.endpoints import admin, auth, config, events, metrics, reports

api_router = APIRouter()

api_router.include_router(auth.router,    prefix="/auth",   tags=["Auth"])
api_router.include_router(admin.router,   prefix="/admin",  tags=["Admin"])
api_router.include_router(reports.router, prefix="",        tags=["Reports"])
api_router.include_router(events.router,                    tags=["Events"])
api_router.include_router(metrics.router,                   tags=["Metrics"])
api_router.include_router(config.router,                    tags=["Config"])
