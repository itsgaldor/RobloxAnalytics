#!/bin/bash
set -e

echo "==> Corriendo migraciones Alembic..."
alembic upgrade head

echo "==> Iniciando servidor uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
