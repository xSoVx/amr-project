FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UVICORN_WORKERS=2 \
    PORT=8080

RUN adduser --disabled-password --gecos '' appuser \
 && apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    gcc \
    g++ \
    libffi-dev \
    libssl-dev \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./pyproject.toml
COPY LICENSE ./LICENSE
COPY amr_engine ./amr_engine
COPY .env.example .env.example

# Install Python dependencies
RUN pip install --upgrade pip \
    && pip install . \
    && pip check

USER appuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --retries=3 CMD curl -f http://127.0.0.1:8080/health || exit 1

CMD ["uvicorn", "amr_engine.main:app", "--host", "0.0.0.0", "--port", "8080"]

# Test stage
FROM python:3.11-slim as test

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN adduser --disabled-password --gecos '' appuser \
 && apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    gcc \
    g++ \
    libffi-dev \
    libssl-dev \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./pyproject.toml
COPY LICENSE ./LICENSE
COPY amr_engine ./amr_engine
COPY tests ./tests
COPY .env.example .env.example

RUN pip install --upgrade pip \
    && pip install .[dev] \
    && pip check

USER appuser

CMD ["pytest", "-v", "--cov=amr_engine", "--cov-fail-under=80"]
