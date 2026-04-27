"""
Tests de los endpoints de Peru City Analytics.
Cubre los 12 casos requeridos en la especificación.
"""
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio


# ---------------------------------------------------------------------------
# 1. GET /metrics?range=day → devuelve las 5 métricas para yape
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_metrics_day_returns_five_metrics(client):
    resp = await client.get("/api/v1/yape/metrics?range=day")
    assert resp.status_code == 200
    body = resp.json()
    assert body["error"] is None

    # Verificar que existen las 5 métricas para public y private
    for server_type in ("public", "private"):
        assert server_type in body["data"]
        metrics = body["data"][server_type]
        assert "sessions" in metrics
        assert "dau" in metrics
        assert "mau" in metrics
        assert "avg_session_minutes" in metrics
        assert "total_hours" in metrics
        assert "time_series" in metrics


# ---------------------------------------------------------------------------
# 2. GET /metrics?range=week → time_series con 7 puntos
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_metrics_week_time_series_has_7_points(client):
    resp = await client.get("/api/v1/yape/metrics?range=week")
    assert resp.status_code == 200
    body = resp.json()

    for server_type in ("public", "private"):
        ts = body["data"][server_type]["time_series"]
        assert len(ts) == 7, f"Expected 7 points for {server_type}, got {len(ts)}"


# ---------------------------------------------------------------------------
# 3. GET /metrics?range=month → time_series con 30 puntos
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_metrics_month_time_series_has_30_points(client):
    resp = await client.get("/api/v1/yape/metrics?range=month")
    assert resp.status_code == 200
    body = resp.json()

    for server_type in ("public", "private"):
        ts = body["data"][server_type]["time_series"]
        assert len(ts) == 30, f"Expected 30 points for {server_type}, got {len(ts)}"


# ---------------------------------------------------------------------------
# 4. GET /metrics/daily?range=week → 7 registros
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_metrics_daily_week_has_7_records(client):
    resp = await client.get("/api/v1/yape/metrics/daily?range=week")
    assert resp.status_code == 200
    body = resp.json()
    assert body["error"] is None
    assert len(body["data"]) == 7

    # Verificar campos requeridos en cada fila
    for row in body["data"]:
        assert "date" in row
        assert "sessions" in row
        assert "unique_users" in row
        assert "avg_minutes" in row
        assert "total_hours" in row
        assert "public_sessions" in row
        assert "private_sessions" in row


# ---------------------------------------------------------------------------
# 5. GET /export.csv → descarga con headers correctos
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_export_csv_correct_headers(client):
    resp = await client.get("/api/v1/yape/export.csv?range=week")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "attachment" in resp.headers["content-disposition"]
    assert "yape" in resp.headers["content-disposition"]
    assert "week" in resp.headers["content-disposition"]

    # Verificar columnas del CSV
    lines = resp.text.strip().split("\n")
    assert len(lines) >= 2  # Header + al menos 1 fila de datos
    header = lines[0]
    for col in ["date", "sessions", "unique_users", "avg_session_minutes", "total_hours", "public_sessions", "private_sessions"]:
        assert col in header, f"Column '{col}' missing from CSV header"


# ---------------------------------------------------------------------------
# 6. POST /events con token válido → 200
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_events_valid_token_returns_200(client, yape_token):
    session_id = uuid.uuid4().hex
    resp = await client.post(
        "/api/v1/yape/events",
        json={
            "event_type": "join",
            "session_id": session_id,
            "user_id_hash": "a" * 64,
            "server_type": "public",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        headers={"X-API-Token": yape_token},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["error"] is None
    assert body["data"]["event"] == "join"


# ---------------------------------------------------------------------------
# 7. POST /events con token inválido → 401
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_events_invalid_token_returns_401(client):
    resp = await client.post(
        "/api/v1/yape/events",
        json={
            "event_type": "join",
            "session_id": uuid.uuid4().hex,
            "user_id_hash": "b" * 64,
            "server_type": "public",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        headers={"X-API-Token": "token-incorrecto-que-no-existe"},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 8. POST /events con brand_slug inexistente → 404
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_events_nonexistent_brand_returns_404(client):
    resp = await client.post(
        "/api/v1/marca-que-no-existe/events",
        json={
            "event_type": "join",
            "session_id": uuid.uuid4().hex,
            "user_id_hash": "c" * 64,
            "server_type": "public",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        headers={"X-API-Token": "cualquier-token"},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 9. GET /config no expone api_token ni universe_id
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_config_does_not_expose_sensitive_fields(client):
    resp = await client.get("/api/v1/yape/config")
    assert resp.status_code == 200
    body = resp.json()
    assert body["error"] is None

    data = body["data"]
    assert "api_token" not in data, "api_token NO debe estar en el response"
    assert "universe_id" not in data, "universe_id NO debe estar en el response"

    # Verificar que sí tiene los campos públicos
    assert "slug" in data
    assert "name" in data
    assert "logo_url" in data
    assert "banner_url" in data
    assert "primary_color" in data


# ---------------------------------------------------------------------------
# 10. GET /config de slug inexistente → 404
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_config_nonexistent_brand_returns_404(client):
    resp = await client.get("/api/v1/marca-fantasma/config")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 11. DAU por día nunca supera sesiones del mismo día (coherencia)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_dau_never_exceeds_sessions_per_day(client):
    resp = await client.get("/api/v1/yape/metrics?range=month")
    assert resp.status_code == 200
    body = resp.json()

    for server_type in ("public", "private"):
        for point in body["data"][server_type]["time_series"]:
            assert point["dau"] <= point["sessions"], (
                f"DAU ({point['dau']}) supera sesiones ({point['sessions']}) "
                f"en {point['date']} para {server_type}"
            )


# ---------------------------------------------------------------------------
# 12. MAU siempre usa ventana de 30 días independiente del range
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_mau_consistent_across_ranges(client):
    """
    El MAU debe ser igual (o muy similar) independientemente del range,
    porque siempre usa la ventana de 30 días.
    """
    resp_day = await client.get("/api/v1/yape/metrics?range=day")
    resp_week = await client.get("/api/v1/yape/metrics?range=week")
    resp_month = await client.get("/api/v1/yape/metrics?range=month")

    assert resp_day.status_code == 200
    assert resp_week.status_code == 200
    assert resp_month.status_code == 200

    mau_day = resp_day.json()["data"]["public"]["mau"]
    mau_week = resp_week.json()["data"]["public"]["mau"]
    mau_month = resp_month.json()["data"]["public"]["mau"]

    # El MAU debe ser el mismo para todos los rangos (ventana fija de 30 días)
    assert mau_day == mau_week == mau_month, (
        f"MAU no es consistente: day={mau_day}, week={mau_week}, month={mau_month}"
    )
