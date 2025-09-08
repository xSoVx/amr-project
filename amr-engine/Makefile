.PHONY: fmt lint test run docker-build docker-run

fmt:
	ruff --fix . || true
	black .
	isort .

lint:
	ruff .
	black --check .
	isort --check-only .

test:
	pytest -q --maxfail=1 --disable-warnings --cov=amr_engine --cov-report=term-missing --cov-fail-under=80

run:
	uvicorn amr_engine.main:app --host 0.0.0.0 --port 8080

docker-build:
	docker build -f docker/Dockerfile -t amr-engine:latest .

docker-run:
	docker run --rm -p 8080:8080 --env-file .env amr-engine:latest

