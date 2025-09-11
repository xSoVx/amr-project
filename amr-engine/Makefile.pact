# Makefile for Pact contract testing
# AMR Classification Service
#
# Usage:
#   make -f Makefile.pact test-consumer    # Run consumer contract tests
#   make -f Makefile.pact publish          # Publish contracts to broker
#   make -f Makefile.pact verify           # Verify provider contracts
#   make -f Makefile.pact can-i-deploy     # Check deployment safety

.PHONY: help test-consumer test-fhir test-hl7v2 test-all publish verify can-i-deploy setup-broker clean

# Default environment variables
PACT_BROKER_URL ?= http://localhost:9292
PACT_CONSUMER_VERSION ?= $(shell git rev-parse --short HEAD)
PACT_PROVIDER_VERSION ?= $(shell git rev-parse --short HEAD)
PACT_BRANCH ?= $(shell git rev-parse --abbrev-ref HEAD)
SERVICE_PORT ?= 8080
PACT_DIR ?= tests/pacts

# Colors for output
GREEN = \033[0;32m
YELLOW = \033[0;33m
RED = \033[0;31m
NC = \033[0m # No Color

help: ## Show this help message
	@echo "Pact Contract Testing Commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-20s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "Environment Variables:"
	@echo "  PACT_BROKER_URL      Pact broker URL (default: http://localhost:9292)"
	@echo "  PACT_BROKER_TOKEN    Authentication token for broker"
	@echo "  PACT_CONSUMER_VERSION Consumer version (default: git commit hash)"
	@echo "  PACT_PROVIDER_VERSION Provider version (default: git commit hash)"
	@echo "  SERVICE_PORT         AMR service port (default: 8080)"

test-consumer: ## Run consumer contract tests for /classify endpoint
	@echo "$(GREEN)Running consumer contract tests for /classify endpoint...$(NC)"
	pytest tests/pact/test_classify_contract.py -v --tb=short

test-fhir: ## Run consumer contract tests for /classify/fhir endpoint
	@echo "$(GREEN)Running consumer contract tests for /classify/fhir endpoint...$(NC)"
	pytest tests/pact/test_classify_fhir_contract.py -v --tb=short

test-hl7v2: ## Run consumer contract tests for /classify/hl7v2 endpoint
	@echo "$(GREEN)Running consumer contract tests for /classify/hl7v2 endpoint...$(NC)"
	pytest tests/pact/test_classify_hl7v2_contract.py -v --tb=short

test-all: ## Run all consumer contract tests
	@echo "$(GREEN)Running all consumer contract tests...$(NC)"
	pytest tests/pact/ -v --tb=short
	@echo "$(GREEN)✓ All consumer tests completed$(NC)"
	@echo "$(YELLOW)Contract files generated in: $(PACT_DIR)$(NC)"
	@ls -la $(PACT_DIR)/*.json 2>/dev/null || echo "No contract files found"

setup-deps: ## Install required dependencies
	@echo "$(GREEN)Installing Pact testing dependencies...$(NC)"
	pip install -e ".[dev]"
	pip install pact-python
	@echo "$(GREEN)✓ Dependencies installed$(NC)"

setup-broker: ## Start local Pact broker with Docker Compose
	@echo "$(GREEN)Starting local Pact broker...$(NC)"
	@python -c "from tests.pact.pact_config import create_docker_compose_pact_broker; open('docker-compose.pact-broker.yml', 'w').write(create_docker_compose_pact_broker())"
	docker-compose -f docker-compose.pact-broker.yml up -d
	@echo "$(GREEN)✓ Pact broker started at http://localhost:9292$(NC)"
	@echo "$(YELLOW)Default credentials: admin/admin$(NC)"

stop-broker: ## Stop local Pact broker
	@echo "$(GREEN)Stopping local Pact broker...$(NC)"
	docker-compose -f docker-compose.pact-broker.yml down
	@echo "$(GREEN)✓ Pact broker stopped$(NC)"

publish: test-all ## Publish contracts to Pact broker
	@echo "$(GREEN)Publishing contracts to Pact broker...$(NC)"
	@if [ -z "$(PACT_BROKER_URL)" ]; then \
		echo "$(RED)Error: PACT_BROKER_URL is required$(NC)"; \
		exit 1; \
	fi
	@if [ ! -f "$(PACT_DIR)"/*.json ]; then \
		echo "$(RED)Error: No contract files found. Run 'make test-all' first.$(NC)"; \
		exit 1; \
	fi
	@python -c "from tests.pact.pact_config import get_pact_publish_command; import subprocess; subprocess.run(get_pact_publish_command(), shell=True, check=True)"
	@echo "$(GREEN)✓ Contracts published successfully$(NC)"

start-service: ## Start AMR service for provider verification
	@echo "$(GREEN)Starting AMR service on port $(SERVICE_PORT)...$(NC)"
	@export AMR_RULES_PATH=amr_engine/rules/eucast_v_2025_1.yaml && \
	export LOG_LEVEL=INFO && \
	export REDIS_ENABLED=false && \
	uvicorn amr_engine.main:app --host 0.0.0.0 --port $(SERVICE_PORT) &
	@sleep 5
	@curl -f http://localhost:$(SERVICE_PORT)/health > /dev/null 2>&1 && \
		echo "$(GREEN)✓ Service started and healthy$(NC)" || \
		(echo "$(RED)✗ Service failed to start or not healthy$(NC)" && exit 1)

stop-service: ## Stop AMR service
	@echo "$(GREEN)Stopping AMR service...$(NC)"
	@pkill -f "uvicorn amr_engine.main:app" || true
	@echo "$(GREEN)✓ Service stopped$(NC)"

verify: ## Verify provider contracts against running service
	@echo "$(GREEN)Verifying provider contracts...$(NC)"
	@if [ -z "$(PACT_BROKER_URL)" ]; then \
		echo "$(RED)Error: PACT_BROKER_URL is required$(NC)"; \
		exit 1; \
	fi
	@curl -f http://localhost:$(SERVICE_PORT)/health > /dev/null 2>&1 || \
		(echo "$(RED)Error: AMR service not running. Run 'make start-service' first.$(NC)" && exit 1)
	@python -c "from tests.pact.pact_config import get_pact_verify_command; import subprocess; subprocess.run(get_pact_verify_command().replace('http://localhost:8080', 'http://localhost:$(SERVICE_PORT)'), shell=True, check=True)"
	@echo "$(GREEN)✓ Provider verification completed$(NC)"

verify-local: start-service verify stop-service ## Start service, verify contracts, then stop service

can-i-deploy: ## Check if it's safe to deploy
	@echo "$(GREEN)Checking deployment safety...$(NC)"
	@if [ -z "$(PACT_BROKER_URL)" ]; then \
		echo "$(RED)Error: PACT_BROKER_URL is required$(NC)"; \
		exit 1; \
	fi
	@python -c "from tests.pact.pact_config import get_can_i_deploy_command; import subprocess; subprocess.run(get_can_i_deploy_command(), shell=True, check=True)"
	@echo "$(GREEN)✓ Safe to deploy$(NC)"

generate-ci: ## Generate CI/CD pipeline configurations
	@echo "$(GREEN)Generating CI/CD pipeline configurations...$(NC)"
	@mkdir -p .github/workflows
	@python -c "from tests.pact.pact_config import create_github_actions_workflow; open('.github/workflows/pact-testing.yml', 'w').write(create_github_actions_workflow())"
	@echo "$(GREEN)✓ GitHub Actions workflow: .github/workflows/pact-testing.yml$(NC)"
	
	@python -c "from tests.pact.pact_config import create_gitlab_ci_pipeline; open('.gitlab-ci.pact.yml', 'w').write(create_gitlab_ci_pipeline())"
	@echo "$(GREEN)✓ GitLab CI pipeline: .gitlab-ci.pact.yml$(NC)"
	
	@python -c "from tests.pact.pact_config import create_jenkins_pipeline; open('Jenkinsfile.pact', 'w').write(create_jenkins_pipeline())"
	@echo "$(GREEN)✓ Jenkins pipeline: Jenkinsfile.pact$(NC)"

clean: ## Clean up generated files and stop services
	@echo "$(GREEN)Cleaning up...$(NC)"
	@rm -rf $(PACT_DIR)/*.json
	@rm -f docker-compose.pact-broker.yml
	@make stop-service
	@make stop-broker
	@echo "$(GREEN)✓ Cleanup completed$(NC)"

clean-all: ## Deep clean including Python cache, logs, and temporary files
	@echo "$(GREEN)Deep cleaning project...$(NC)"
	@python ../scripts/cleanup.py --categories all --keep-pacts
	@make clean
	@echo "$(GREEN)✓ Deep cleanup completed$(NC)"

status: ## Show current status
	@echo "$(GREEN)Pact Testing Status:$(NC)"
	@echo ""
	@echo "Environment:"
	@echo "  PACT_BROKER_URL:      $(PACT_BROKER_URL)"
	@echo "  PACT_CONSUMER_VERSION: $(PACT_CONSUMER_VERSION)"
	@echo "  PACT_PROVIDER_VERSION: $(PACT_PROVIDER_VERSION)"
	@echo "  PACT_BRANCH:          $(PACT_BRANCH)"
	@echo "  SERVICE_PORT:         $(SERVICE_PORT)"
	@echo ""
	@echo "Contract Files:"
	@ls -la $(PACT_DIR)/*.json 2>/dev/null || echo "  No contract files found"
	@echo ""
	@echo "Service Health:"
	@curl -f http://localhost:$(SERVICE_PORT)/health > /dev/null 2>&1 && \
		echo "  ✓ AMR service is running and healthy" || \
		echo "  ✗ AMR service is not running or unhealthy"
	@echo ""
	@echo "Broker Health:"
	@curl -f $(PACT_BROKER_URL)/diagnostic/status/heartbeat > /dev/null 2>&1 && \
		echo "  ✓ Pact broker is accessible" || \
		echo "  ✗ Pact broker is not accessible"

# Full workflow targets
full-test: test-all publish verify can-i-deploy ## Run complete Pact testing workflow
	@echo "$(GREEN)✓ Complete Pact testing workflow completed successfully$(NC)"

# Development workflow
dev-setup: setup-deps setup-broker ## Set up development environment
	@echo "$(GREEN)✓ Development environment ready$(NC)"
	@echo "$(YELLOW)Next steps:$(NC)"
	@echo "  1. Run 'make test-all' to execute consumer tests"
	@echo "  2. Run 'make start-service' to start the AMR service"
	@echo "  3. Run 'make verify' to verify provider contracts"

# Example workflow for new developers
example: ## Run example workflow for new developers
	@echo "$(GREEN)Running example Pact testing workflow...$(NC)"
	@echo ""
	@echo "$(YELLOW)Step 1: Setting up dependencies...$(NC)"
	@make setup-deps
	@echo ""
	@echo "$(YELLOW)Step 2: Running consumer tests...$(NC)"
	@make test-all
	@echo ""
	@echo "$(YELLOW)Step 3: Starting AMR service...$(NC)"
	@make start-service
	@echo ""
	@echo "$(YELLOW)Step 4: Verifying provider contracts...$(NC)"
	@make verify-local
	@echo ""
	@echo "$(GREEN)✓ Example workflow completed successfully!$(NC)"
	@echo "$(YELLOW)Check the generated contract files in: $(PACT_DIR)$(NC)"