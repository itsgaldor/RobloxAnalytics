# Peru City Analytics — Backend v0.1.0

Dashboard SaaS multi-tenant que muestra métricas de experiencias Roblox a marcas que activan campañas en la plataforma. Esta es la iteración 00: backend completo con data falsa, listo para ser consumido por el frontend.

---

## Prerequisitos

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) instalado y corriendo

---

## Setup en 3 comandos

```bash
cp backend/.env.example backend/.env
docker-compose up --build -d
docker-compose exec api python seed.py
```

---

## Verificación

Abrí el explorador de la API en tu navegador:

```
http://localhost:8000/docs
```

---

## Correr tests

```bash
docker-compose exec api pytest -v
```

---

## Endpoints disponibles

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `POST` | `/api/v1/{brand_slug}/events` | Recibe eventos del Script de Roblox (join, leave, heartbeat). Requiere header `X-API-Token`. |
| `GET` | `/api/v1/{brand_slug}/metrics?range=day\|week\|month` | Métricas completas del dashboard separadas por server_type. |
| `GET` | `/api/v1/{brand_slug}/metrics/daily?range=week\|month` | Array de métricas por día con sesiones públicas y privadas. |
| `GET` | `/api/v1/{brand_slug}/export.csv?range=day\|week\|month` | Exporta métricas en CSV. |
| `POST` | `/api/v1/{brand_slug}/refresh` | Placeholder para invalidación de caché futura. |
| `GET` | `/api/v1/{brand_slug}/config` | Configuración pública de la marca (sin api_token ni universe_id). |
| `GET` | `/health` | Healthcheck del servicio. |

### Marcas de ejemplo (creadas por el seed)

| Slug | Descripción |
|------|-------------|
| `yape` | Yape — 30 días de data, ~800-1400 sesiones/día en fines de semana |
| `demo` | Marca Demo — 30 días de data, ~200-500 sesiones/día en fines de semana |

### Curl de ejemplo

```bash
# Métricas de Yape (último mes)
curl -s "http://localhost:8000/api/v1/yape/metrics?range=month" | python -m json.tool

# Configuración pública de Demo
curl -s "http://localhost:8000/api/v1/demo/config" | python -m json.tool

# Exportar CSV de la semana
curl -o yape_week.csv "http://localhost:8000/api/v1/yape/export.csv?range=week"
```

---

## Estructura de carpetas

```
peru-city-analytics/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app, lifespan, middlewares
│   │   ├── config.py            # Settings desde .env con pydantic-settings
│   │   ├── dependencies.py      # Deps compartidas (get_db, get_brand, auth)
│   │   ├── api/v1/
│   │   │   ├── router.py        # Agrupa todos los routers de v1
│   │   │   └── endpoints/
│   │   │       ├── events.py    # POST /{brand_slug}/events
│   │   │       ├── metrics.py   # GET /{brand_slug}/metrics, /daily, /export.csv, /refresh
│   │   │       └── config.py    # GET /{brand_slug}/config
│   │   ├── models/
│   │   │   └── models.py        # SQLAlchemy models: Brand, Session
│   │   ├── schemas/
│   │   │   ├── events.py        # EventIn, EventType enum
│   │   │   ├── metrics.py       # MetricsResponse, DailyRow, TimeSeries
│   │   │   └── config.py        # BrandConfig (sin api_token ni universe_id)
│   │   ├── services/
│   │   │   ├── metrics.py       # Cálculo DAU, MAU, sesiones, tiempos
│   │   │   └── export.py        # Generación CSV
│   │   └── db/
│   │       └── database.py      # AsyncEngine, AsyncSession, Base
│   ├── migrations/              # Alembic: migraciones de la DB
│   ├── tests/
│   │   ├── conftest.py          # Fixtures: test client, test DB SQLite, marcas
│   │   └── test_endpoints.py    # 12 tests de los endpoints
│   ├── seed.py                  # Genera 30 días de data falsa (idempotente)
│   ├── requirements.txt
│   ├── .env.example
│   ├── alembic.ini
│   └── Dockerfile
├── docker-compose.yml
└── README.md
```

---

## Decisiones de diseño

- **Privacidad by design**: `user_id_hash` es SHA-256 del userId de Roblox. Nunca se almacena ni expone el ID real.
- **MAU ventana fija**: El MAU siempre calcula los últimos 30 días, independientemente del `range` solicitado.
- **Solo sesiones completadas para tiempos**: `avg_session_minutes` y `total_hours` solo consideran sesiones con `left_at NOT NULL`.
- **Idempotencia del seed**: Correr `seed.py` múltiples veces borra y recrea la data, nunca duplica.
- **Tests con SQLite**: Los tests usan SQLite in-memory (sin Docker) para ser rápidos y portables.

---

## Deploy en Railway

### Prerequisitos
- Cuenta en [Railway](https://railway.app)
- Repo en GitHub conectado a Railway

### Pasos

1. Crear nuevo proyecto en Railway → **"Deploy from GitHub repo"**
2. Seleccionar el repo `RobloxAnalytics`
3. Railway detecta el `railway.toml` automáticamente
4. Agregar servicio PostgreSQL:
   - Click en **"+ New"** → **"Database"** → **"PostgreSQL"**
   - Railway conecta la DB y expone `DATABASE_URL` automáticamente
5. Configurar variables de entorno en el servicio principal:

   | Variable | Valor |
   |---|---|
   | `DATABASE_URL` | Copiar de la DB PostgreSQL de Railway (cambiar `postgresql://` → `postgresql+asyncpg://`) |
   | `ENVIRONMENT` | `production` |
   | `ALLOWED_ORIGINS` | `https://tu-app.up.railway.app` |
   | `ANTHROPIC_API_KEY` | Opcional — dejar vacío para análisis simulado |

6. Deploy automático al hacer push a `main`

### Primera vez — ejecutar seed en producción

```bash
railway run python seed.py
```

### URLs en producción

| Recurso | URL |
|---|---|
| Dashboard | `https://tu-app.up.railway.app/dashboard/?brand=yape` |
| Admin | `https://tu-app.up.railway.app/admin/` |
| API Docs | `https://tu-app.up.railway.app/docs` |
| Health | `https://tu-app.up.railway.app/health` |

### Nota sobre DATABASE_URL

Railway genera la URL en formato `postgresql://`. El proyecto usa `asyncpg`, así que debes cambiar el prefijo manualmente:

```
postgresql://user:pass@host:5432/db
        ↓
postgresql+asyncpg://user:pass@host:5432/db
```
