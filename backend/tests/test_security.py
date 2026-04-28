"""
Tests de seguridad para Peru City Analytics.
Verifica rate limiting, validación de payload, autenticación y headers.
"""
import time

import pytest


# ── Helpers ───────────────────────────────────────────────────────────────────

def _valid_payload(overrides: dict = {}) -> dict:
    """Payload válido base para los tests de eventos."""
    base = {
        "event_type":   "join",
        "session_id":   "test-session-abc123",
        "user_id_hash": "hashvalue-abc123",
        "server_type":  "public",
        "timestamp":    int(time.time()),
    }
    base.update(overrides)
    return base


# ── Validación de payload ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_events_invalid_event_type(client, seed_data):
    """event_type con valor no permitido devuelve 422."""
    token = seed_data["yape"].api_token
    resp = await client.post(
        "/api/v1/yape/events",
        json=_valid_payload({"event_type": "invalid_type"}),
        headers={"X-API-Token": token},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_events_sql_injection_session_id(client, seed_data):
    """SQL injection en session_id es rechazado con 422."""
    token = seed_data["yape"].api_token
    resp = await client.post(
        "/api/v1/yape/events",
        json=_valid_payload({"session_id": "'; DROP TABLE sessions; --"}),
        headers={"X-API-Token": token},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_events_special_chars_user_hash(client, seed_data):
    """Caracteres especiales en user_id_hash son rechazados con 422."""
    token = seed_data["yape"].api_token
    resp = await client.post(
        "/api/v1/yape/events",
        json=_valid_payload({"user_id_hash": "<script>alert(1)</script>"}),
        headers={"X-API-Token": token},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_events_future_timestamp(client, seed_data):
    """Timestamp muy en el futuro (>5 min) es rechazado con 422."""
    token = seed_data["yape"].api_token
    resp = await client.post(
        "/api/v1/yape/events",
        json=_valid_payload({"timestamp": int(time.time()) + 9999}),
        headers={"X-API-Token": token},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_events_old_timestamp(client, seed_data):
    """Timestamp de hace 10 minutos (>5 min) es rechazado con 422."""
    token = seed_data["yape"].api_token
    resp = await client.post(
        "/api/v1/yape/events",
        json=_valid_payload({"timestamp": int(time.time()) - 700}),
        headers={"X-API-Token": token},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_events_session_id_too_short(client, seed_data):
    """session_id menor a 8 chars devuelve 422."""
    token = seed_data["yape"].api_token
    resp = await client.post(
        "/api/v1/yape/events",
        json=_valid_payload({"session_id": "abc"}),
        headers={"X-API-Token": token},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_events_invalid_server_type(client, seed_data):
    """server_type con valor distinto de public/private devuelve 422."""
    token = seed_data["yape"].api_token
    resp = await client.post(
        "/api/v1/yape/events",
        json=_valid_payload({"server_type": "vip"}),
        headers={"X-API-Token": token},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_events_extra_fields_ignored(client, seed_data):
    """Campos extra en el payload son ignorados silenciosamente (no 422)."""
    token = seed_data["yape"].api_token
    payload = _valid_payload({"campo_extra": "valor", "otro": 123})
    payload["session_id"] = "extra-fields-test-ok"
    resp = await client.post(
        "/api/v1/yape/events",
        json=payload,
        headers={"X-API-Token": token},
    )
    # Puede ser 200 (join aceptado) o 409 (si ya existe), nunca 422
    assert resp.status_code in (200, 201, 409)


# ── Autenticación ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_events_wrong_token(client, seed_data):
    """Token incorrecto devuelve 401."""
    resp = await client.post(
        "/api/v1/yape/events",
        json=_valid_payload(),
        headers={"X-API-Token": "token-completamente-incorrecto"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_events_missing_token(client, seed_data):
    """Sin token devuelve 422 (header requerido faltante)."""
    resp = await client.post(
        "/api/v1/yape/events",
        json=_valid_payload(),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_events_wrong_brand(client, seed_data):
    """Token de demo rechazado para slug yape → 401."""
    demo_token = seed_data["demo"].api_token
    resp = await client.post(
        "/api/v1/yape/events",
        json=_valid_payload(),
        headers={"X-API-Token": demo_token},
    )
    assert resp.status_code == 401


# ── Acceso al dashboard y admin ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_metrics_endpoint_public(client, seed_data):
    """El endpoint de métricas es público (no requiere auth)."""
    resp = await client.get("/api/v1/yape/metrics?range=week")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_config_endpoint_public(client, seed_data):
    """El endpoint de config es público."""
    resp = await client.get("/api/v1/yape/config")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_admin_protected(client):
    """El admin API SÍ requiere auth — devuelve 401 sin cookie."""
    resp = await client.get("/api/v1/admin/brands")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_admin_root_redirect(client):
    """GET /admin/ sin sesión redirige a login."""
    resp = await client.get("/admin/", follow_redirects=False)
    assert resp.status_code in (301, 302, 307, 308)
    assert "login" in resp.headers.get("location", "").lower()


# ── Security headers ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_security_headers_present(client):
    """Los headers de seguridad están presentes en las respuestas."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert resp.headers.get("X-XSS-Protection") == "1; mode=block"
    assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"


# ── Evento válido completo ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_events_valid_join(client, seed_data):
    """Evento join válido con token correcto devuelve 200."""
    token = seed_data["yape"].api_token
    resp = await client.post(
        "/api/v1/yape/events",
        json=_valid_payload({"session_id": "security-test-session-001"}),
        headers={"X-API-Token": token},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["data"]["event"] == "join"
