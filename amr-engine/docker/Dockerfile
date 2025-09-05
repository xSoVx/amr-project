FROM python:3.11-slim@sha256:88d952f5a7eecaa04d3d0d457f7d4e3a0bc940fb0f2dbf3f1483e8d6e8c9226b

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UVICORN_WORKERS=2 \
    PORT=8080

RUN adduser --disabled-password --gecos '' appuser \
 && apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY amr-engine/pyproject.toml ./pyproject.toml
COPY amr-engine/README.md ./README.md
COPY amr-engine/LICENSE ./LICENSE
COPY amr-engine/amr_engine ./amr_engine
COPY amr-engine/.env.example .env.example || true

RUN pip install --upgrade pip \
    && pip install . \
    && pip check

USER appuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --retries=3 CMD curl -f http://127.0.0.1:8080/healthz || exit 1

CMD ["uvicorn", "amr_engine.main:app", "--host", "0.0.0.0", "--port", "8080"]
