"""
Schemas Pydantic para las respuestas de métricas del dashboard.
"""
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class TimeSeriesPoint(BaseModel):
    """Un punto en la serie temporal: métricas de un día específico."""
    date: date
    sessions: int
    dau: int = Field(..., description="Usuarios únicos en ese día")
    avg_minutes: float = Field(..., description="Promedio de duración de sesión en minutos")


class ServerTypeMetrics(BaseModel):
    """Métricas agregadas para un tipo de servidor (public o private)."""
    sessions: int = Field(..., description="Total de sesiones en el rango")
    dau: float = Field(..., description="Promedio de usuarios únicos por día en el rango")
    mau: int = Field(..., description="Usuarios únicos en los últimos 30 días (siempre)")
    avg_session_minutes: float = Field(..., description="Promedio de duración de sesión en minutos")
    total_hours: float = Field(..., description="Suma total de horas de juego")
    time_series: list[TimeSeriesPoint] = Field(default_factory=list)


class PreviousMetrics(BaseModel):
    """Métricas combinadas del período anterior para calcular variación %."""
    sessions: int
    dau: float
    mau: int
    avg_session_minutes: float
    total_hours: float


class MetricsData(BaseModel):
    """Contenedor de métricas con public, private y previous opcional."""
    public: ServerTypeMetrics
    private: ServerTypeMetrics
    previous: PreviousMetrics | None = None


class MetricsResponse(BaseModel):
    """Respuesta completa de métricas, separada por tipo de servidor."""
    data: MetricsData
    meta: dict = {}
    error: str | None = None


class DailyRow(BaseModel):
    """Una fila del reporte diario."""
    date: date
    sessions: int
    unique_users: int
    avg_minutes: float
    total_hours: float
    public_sessions: int
    private_sessions: int


class DailyMetricsResponse(BaseModel):
    """Respuesta del endpoint de métricas diarias."""
    data: list[DailyRow]
    meta: dict = {}
    error: str | None = None


RangeType = Literal["day", "week", "month"]
DailyRangeType = Literal["week", "month"]
