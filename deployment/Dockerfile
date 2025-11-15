# Dockerfile para FastAPI Backend
# Multi-stage build para reducir tamaño

FROM python:3.11-slim as builder

WORKDIR /app

# Instalar dependencias build
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements
COPY pyproject.toml pyproject.toml

# Crear virtual env
RUN python -m pip install --upgrade pip && \
    pip install -e .

# ============================================================================
# Stage de Producción
# ============================================================================
FROM python:3.11-slim

WORKDIR /app

# Metadatos
LABEL maintainer="Org-Assistant Team"
LABEL description="FastAPI Backend for Org-Assistant RAG"

# Instalar runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Crear usuario no-root para seguridad
RUN useradd -m -u 1000 appuser

# Copiar código
COPY . .

# Copiar virtual env del builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Crear directorios de datos
RUN mkdir -p /data/embeddings/chroma /data/auth /data/analytics /data/sessions /data/processed /data/raw /data/encrypted_keys /app/logs && \
    chown -R appuser:appuser /data /app/logs

# Cambiar usuario
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:${SERVICE_PORT:-8000}/health || exit 1

# Exponer puerto
EXPOSE 8000

# Comando de inicio
CMD ["python", "-m", "uvicorn", "src.service.app:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "4"]
