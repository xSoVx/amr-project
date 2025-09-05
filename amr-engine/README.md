AMR Engine (FastAPI, Python 3.11)

Production-ready microservice for Antimicrobial Resistance (AMR) classification. Receives FHIR R4 Observations/Bundle, applies EUCAST/CLSI-style rules (from versioned YAML/JSON), and returns S/I/R/RR decisions with reasoning.

Quickstart
- python -m venv .venv && . .venv/bin/activate
- pip install -e .
- uvicorn amr_engine.main:app --host 0.0.0.0 --port 8080

Docker
- docker build -f docker/Dockerfile -t amr-engine:latest .
- docker run -p 8080:8080 --env-file .env amr-engine:latest
- or docker compose -f docker/docker-compose.yml up --build

Tests
- pytest -q --maxfail=1 --disable-warnings

Env Vars (.env.example)
- AMR_RULES_PATH: path to rules directory or file
- ADMIN_TOKEN: token for /admin/rules/reload
- SERVICE_NAME: default amr-engine
- LOG_LEVEL: INFO|DEBUG|WARNING|ERROR
- EUST_VER: optional rules version label

Endpoints
- POST /classify: Accepts FHIR Bundle or array of Observations. Returns list of decisions with reasoning.
- POST /rules/dry-run: Evaluate ad-hoc input against loaded rules (debugging).
- GET /healthz, GET /version, GET /metrics

Security
- No secrets in repo. Non-root Docker user. Minimal dependencies. Token-protected admin reload.

Notes
- Rules validated at startup against JSON Schema. Hot-reload via SIGHUP or POST /admin/rules/reload.
- Structured JSON logs with request id and classification summary.

