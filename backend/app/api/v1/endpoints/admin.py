"""
Endpoints de administración del backoffice Peru City Analytics.
Prefijo: /api/v1/admin

Endpoints:
  GET    /brands                        — lista todas las marcas con métricas
  POST   /brands                        — crear nueva marca
  GET    /brands/{slug}                 — detalle de una marca
  PUT    /brands/{slug}                 — actualizar marca
  DELETE /brands/{slug}                 — soft delete (active=False)
  POST   /brands/{slug}/regenerate-token — regenerar api_token
  GET    /brands/{slug}/script          — generar Script de Lua
"""
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Request,  APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.models.models import Brand
from app.services.metrics import get_combined_aggregate, _get_date_range

router = APIRouter()

# ──────────────────────────────────────────────────────────────────────────────
# SCHEMAS PYDANTIC
# ──────────────────────────────────────────────────────────────────────────────

class WeekMetrics(BaseModel):
    sessions: int
    dau: float
    mau: int
    avg_session_minutes: float
    total_hours: float


class BrandAdminOut(BaseModel):
    """Representación completa de una marca para el backoffice."""
    id: str
    slug: str
    name: str
    primary_color: str
    logo_url: Optional[str] = None
    banner_url: Optional[str] = None
    universe_id: Optional[str] = None
    api_token: str
    active: bool
    created_at: datetime
    last_event_at: Optional[datetime] = None
    health: str          # "ok" | "warning" | "offline"
    week_metrics: WeekMetrics


class BrandCreateIn(BaseModel):
    """Payload para crear una nueva marca."""
    name: str = Field(..., min_length=1, max_length=100)
    slug: str = Field(..., min_length=1, max_length=50)
    primary_color: str = Field(default="#000000")
    logo_url: Optional[str] = None
    banner_url: Optional[str] = None
    universe_id: Optional[str] = None

    @field_validator("slug")
    @classmethod
    def slug_must_be_valid(cls, v: str) -> str:
        """El slug solo puede contener letras minúsculas, números y guiones."""
        if not re.match(r"^[a-z0-9-]+$", v):
            raise ValueError("El slug solo puede contener letras minúsculas (a-z), números (0-9) y guiones (-).")
        return v

    @field_validator("primary_color")
    @classmethod
    def color_must_be_hex(cls, v: str) -> str:
        if not re.match(r"^#[0-9A-Fa-f]{6}$", v):
            raise ValueError("El color debe ser un hex válido (#RRGGBB).")
        return v


class BrandUpdateIn(BaseModel):
    """Payload para actualizar una marca (slug no editable)."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    primary_color: Optional[str] = None
    logo_url: Optional[str] = None
    banner_url: Optional[str] = None
    universe_id: Optional[str] = None

    @field_validator("primary_color")
    @classmethod
    def color_must_be_hex(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not re.match(r"^#[0-9A-Fa-f]{6}$", v):
            raise ValueError("El color debe ser un hex válido (#RRGGBB).")
        return v


# ──────────────────────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────────────────────

def _compute_health(last_event_at: Optional[datetime]) -> str:
    """
    Calcula el estado de salud de la marca según la antigüedad del último evento.
    - "ok"      → evento recibido hace menos de 2 horas
    - "warning" → evento recibido hace 2-24 horas
    - "offline" → no hay eventos o el último fue hace más de 24 horas
    """
    if last_event_at is None:
        return "offline"
    # Asegurar que tiene timezone para comparar
    if last_event_at.tzinfo is None:
        last_event_at = last_event_at.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - last_event_at
    if delta < timedelta(hours=2):
        return "ok"
    if delta < timedelta(hours=24):
        return "warning"
    return "offline"


async def _build_brand_out(db: AsyncSession, brand: Brand) -> BrandAdminOut:
    """Construye el objeto BrandAdminOut con métricas de la última semana."""
    week_start, week_end = _get_date_range("week")
    metrics = await get_combined_aggregate(db, brand.id, week_start, week_end)
    return BrandAdminOut(
        id=str(brand.id),
        slug=brand.slug,
        name=brand.name,
        primary_color=brand.primary_color,
        logo_url=brand.logo_url,
        banner_url=brand.banner_url,
        universe_id=brand.universe_id,
        api_token=brand.api_token,
        active=brand.active,
        created_at=brand.created_at,
        last_event_at=brand.last_event_at,
        health=_compute_health(brand.last_event_at),
        week_metrics=WeekMetrics(**metrics),
    )


LUA_SCRIPT_TEMPLATE = """\
-- ============================================
-- Peru City Analytics - Script de tracking
-- Marca: {brand_name}
-- Generado: {generated_at}
-- NO compartir este script publicamente
-- ============================================

local HttpService = game:GetService("HttpService")
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")

-- Configuracion
local API_URL = "{api_url}/api/v1/{brand_slug}/events"
local API_TOKEN = "{api_token}"
local HEARTBEAT_INTERVAL = 60  -- segundos

-- Funcion para hashear userId (SHA-256 simplificado via string encoding)
local function hashUserId(userId)
    -- Combinamos userId con un salt fijo para anonimizar
    return HttpService:GenerateGUID(false):sub(1,8) .. tostring(userId):sub(-4)
end

-- Detectar tipo de servidor
local function getServerType()
    if game.PrivateServerId ~= "" and game.PrivateServerOwnerId ~= 0 then
        return "private"
    else
        return "public"
    end
end

-- Enviar evento al backend
local function sendEvent(eventType, sessionId, userIdHash)
    local success, err = pcall(function()
        HttpService:PostAsync(API_URL, HttpService:JSONEncode({{
            event_type = eventType,
            session_id = sessionId,
            user_id_hash = userIdHash,
            server_type = getServerType(),
            timestamp = os.time()
        }}), Enum.HttpContentType.ApplicationJson, false, {{
            ["X-API-Token"] = API_TOKEN
        }})
    end)
    if not success then
        warn("[PCA] Error enviando evento " .. eventType .. ": " .. tostring(err))
    end
end

-- Tracking por jugador
local function trackPlayer(player)
    local userIdHash = hashUserId(player.UserId)
    local sessionId = HttpService:GenerateGUID(false)
    local heartbeatConnection

    -- Evento JOIN
    sendEvent("join", sessionId, userIdHash)

    -- Heartbeat cada 60 segundos
    local lastHeartbeat = os.time()
    heartbeatConnection = RunService.Heartbeat:Connect(function()
        if os.time() - lastHeartbeat >= HEARTBEAT_INTERVAL then
            lastHeartbeat = os.time()
            sendEvent("heartbeat", sessionId, userIdHash)
        end
    end)

    -- Evento LEAVE
    player.AncestryChanged:Connect(function()
        if not player:IsDescendantOf(game) then
            if heartbeatConnection then
                heartbeatConnection:Disconnect()
            end
            sendEvent("leave", sessionId, userIdHash)
        end
    end)
end

-- Inicializar para jugadores ya conectados y nuevos
Players.PlayerAdded:Connect(trackPlayer)
for _, player in ipairs(Players:GetPlayers()) do
    trackPlayer(player)
end

print("[PCA] Peru City Analytics activo - Marca: {brand_name}")
"""


def _generate_lua_script(brand: Brand, api_url: str) -> str:
    """Rellena el template Lua con los datos de la marca."""
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return LUA_SCRIPT_TEMPLATE.format(
        brand_name=brand.name,
        generated_at=generated_at,
        api_url=api_url.rstrip("/"),
        brand_slug=brand.slug,
        api_token=brand.api_token,
    )


# ──────────────────────────────────────────────────────────────────────────────
# ENDPOINTS
# ──────────────────────────────────────────────────────────────────────────────

@router.get(
    "/brands",
    summary="Listar todas las marcas",
    description="Devuelve todas las marcas (activas e inactivas) con métricas de la última semana y health status.",
)
async def list_brands(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Brand).order_by(Brand.created_at.desc()))
    brands = result.scalars().all()

    data = []
    for brand in brands:
        data.append((await _build_brand_out(db, brand)).model_dump())

    return {"data": data, "meta": {"total": len(data)}, "error": None}


@router.post(
    "/brands",
    status_code=201,
    summary="Crear nueva marca",
    description="Crea una marca nueva. api_token se genera automáticamente. Error 409 si el slug ya existe.",
)
async def create_brand(body: BrandCreateIn, db: AsyncSession = Depends(get_db)):
    # Verificar unicidad del slug
    existing = await db.execute(select(Brand).where(Brand.slug == body.slug))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail={"data": None, "meta": {}, "error": f"El slug '{body.slug}' ya está en uso."},
        )

    new_brand = Brand(
        id=uuid.uuid4(),
        slug=body.slug,
        name=body.name,
        primary_color=body.primary_color,
        logo_url=body.logo_url,
        banner_url=body.banner_url,
        universe_id=body.universe_id,
        api_token="rblx_" + secrets.token_urlsafe(32),
        active=True,
    )
    db.add(new_brand)
    await db.commit()
    await db.refresh(new_brand)

    out = await _build_brand_out(db, new_brand)
    return {"data": out.model_dump(), "meta": {}, "error": None}


@router.get(
    "/brands/{brand_slug}",
    summary="Detalle de una marca",
    description="Devuelve el detalle completo de una marca incluyendo api_token.",
)
async def get_brand_detail(brand_slug: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Brand).where(Brand.slug == brand_slug))
    brand = result.scalar_one_or_none()
    if brand is None:
        raise HTTPException(
            status_code=404,
            detail={"data": None, "meta": {}, "error": f"Marca '{brand_slug}' no encontrada."},
        )
    out = await _build_brand_out(db, brand)
    return {"data": out.model_dump(), "meta": {}, "error": None}


@router.put(
    "/brands/{brand_slug}",
    summary="Actualizar marca",
    description="Actualiza los campos editables de una marca. El slug y el api_token no son modificables aquí.",
)
async def update_brand(brand_slug: str, body: BrandUpdateIn, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Brand).where(Brand.slug == brand_slug))
    brand = result.scalar_one_or_none()
    if brand is None:
        raise HTTPException(
            status_code=404,
            detail={"data": None, "meta": {}, "error": f"Marca '{brand_slug}' no encontrada."},
        )

    # Actualizar solo los campos enviados (PATCH-style dentro de PUT)
    if body.name is not None:
        brand.name = body.name
    if body.primary_color is not None:
        brand.primary_color = body.primary_color
    if body.logo_url is not None:
        brand.logo_url = body.logo_url
    if body.banner_url is not None:
        brand.banner_url = body.banner_url
    if body.universe_id is not None:
        brand.universe_id = body.universe_id

    await db.commit()
    await db.refresh(brand)
    out = await _build_brand_out(db, brand)
    return {"data": out.model_dump(), "meta": {}, "error": None}


@router.delete(
    "/brands/{brand_slug}",
    summary="Desactivar marca (soft delete)",
    description="Marca la marca como inactiva (active=False). Los datos históricos se conservan.",
)
async def deactivate_brand(brand_slug: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Brand).where(Brand.slug == brand_slug))
    brand = result.scalar_one_or_none()
    if brand is None:
        raise HTTPException(
            status_code=404,
            detail={"data": None, "meta": {}, "error": f"Marca '{brand_slug}' no encontrada."},
        )
    brand.active = False
    await db.commit()
    return {
        "data": {"slug": brand_slug, "active": False},
        "meta": {},
        "error": None,
    }


@router.post(
    "/brands/{brand_slug}/regenerate-token",
    summary="Regenerar API token",
    description=(
        "Genera un nuevo api_token para la marca. "
        "ACCIÓN DESTRUCTIVA: el Script de Roblox instalado dejará de funcionar "
        "hasta que se actualice con el nuevo token."
    ),
)
async def regenerate_token(brand_slug: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Brand).where(Brand.slug == brand_slug))
    brand = result.scalar_one_or_none()
    if brand is None:
        raise HTTPException(
            status_code=404,
            detail={"data": None, "meta": {}, "error": f"Marca '{brand_slug}' no encontrada."},
        )
    new_token = "rblx_" + secrets.token_urlsafe(32)
    brand.api_token = new_token
    await db.commit()
    return {
        "data": {
            "slug": brand_slug,
            "api_token": new_token,
            "regenerated_at": datetime.now(timezone.utc).isoformat(),
        },
        "meta": {},
        "error": None,
    }


@router.get(
    "/brands/{brand_slug}/script",
    summary="Generar Script de Lua",
    description="Genera y devuelve el Script de Lua listo para instalar en Roblox Studio.",
)
async def get_script(
    brand_slug: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Brand).where(Brand.slug == brand_slug))
    brand = result.scalar_one_or_none()
    if brand is None:
        raise HTTPException(
            status_code=404,
            detail={"data": None, "meta": {}, "error": f"Marca '{brand_slug}' no encontrada."},
        )

    # En produccion se construye la URL desde el header Host del request.
    # En desarrollo se usa API_BASE_URL del .env.
    from app.config import settings
    if settings.ENVIRONMENT == "production":
        scheme = request.headers.get("x-forwarded-proto", "https")
        host   = request.headers.get("host", "")
        api_url = f"{scheme}://{host}"
    else:
        api_url = settings.API_BASE_URL

    script = _generate_lua_script(brand, api_url)
    return {
        "data": {
            "script": script,
            "brand_slug": brand.slug,
            "api_token": brand.api_token,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "meta": {},
        "error": None,
    }
