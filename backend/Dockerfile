FROM python:3.11-slim

# Variables de entorno para Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

# Instalar dependencias del sistema necesarias para asyncpg y ReportLab
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# El build context es el ROOT del repo.
# Instalar dependencias primero (capa cacheada)
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copiar el backend al workdir
COPY backend/ .

# Copiar el frontend para que main.py lo sirva como estáticos
COPY frontend/ frontend/

# Exponer el puerto
EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Hacer ejecutable el startup script
RUN chmod +x startup.sh

# Corre migraciones y levanta el servidor
CMD ["/bin/bash", "startup.sh"]
