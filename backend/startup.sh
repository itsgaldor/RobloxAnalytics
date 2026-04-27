#!/bin/bash
set -e

echo "==> Entorno: ${ENVIRONMENT:-development}"

if [ -z "$DATABASE_URL" ]; then
  echo "ERROR: La variable DATABASE_URL no esta configurada."
  echo "  En Railway: servicio web -> Variables -> agregar DATABASE_URL"
  echo "  referenciando el servicio PostgreSQL con: \${{Postgres.DATABASE_URL}}"
  exit 1
fi

echo "==> DATABASE_URL detectada (host: $(echo $DATABASE_URL | sed 's/.*@//' | sed 's/\/.*//'))"

echo "==> Corriendo migraciones Alembic..."
alembic upgrade head

echo "==> Iniciando servidor uvicorn en puerto ${PORT:-8000}..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
