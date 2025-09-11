# Provider Verification Quick Start Guide

## Setup (One-time)

```bash
# Install dependencies
pip install -e ".[dev]"

# Set environment variables
export TESTING=true
export PACT_VERIFICATION=true
export AMR_RULES_PATH=amr_engine/rules/eucast_v_2025_1.yaml

# Optional: Pact broker configuration
export PACT_BROKER_URL=https://your-pact-broker.com
export PACT_BROKER_TOKEN=your-token
```

## Start AMR Service

```bash
# Start service with provider state endpoints
uvicorn amr_engine.main:app --host 0.0.0.0 --port 8080
```

## Run Tests

### All Provider Verification Tests
```bash
pytest tests/pact/test_provider_verification.py -v
```

### Specific Consumer Tests
```bash
pytest tests/pact/test_provider_verification.py --consumer-name=ui-service -v
```

### Async Scenario Tests
```bash
pytest tests/pact/test_async_scenarios.py -v
```

### With Debug Output
```bash
pytest tests/pact/ -v -s --log-cli-level=DEBUG
```

## Verify Against Pact Broker

```bash
# All consumers
pact-broker verify \
  --provider amr-classification-service \
  --provider-base-url http://localhost:8080 \
  --broker-base-url $PACT_BROKER_URL \
  --broker-token $PACT_BROKER_TOKEN \
  --publish-verification-results

# Specific consumer
pact-broker verify \
  --provider amr-classification-service \
  --consumer ui-service \
  --provider-base-url http://localhost:8080 \
  --broker-base-url $PACT_BROKER_URL \
  --publish-verification-results
```

## Health Checks

```bash
# Service health
curl http://localhost:8080/health

# Pact verification health  
curl http://localhost:8080/_pact/health

# Available provider states
curl http://localhost:8080/_pact/provider-states
```

## Common Commands

```bash
# Check deployment safety
pact-broker can-i-deploy \
  --pacticipant amr-consumer \
  --version 1.0.0 \
  --pacticipant amr-classification-service \
  --version 1.0.0 \
  --broker-base-url $PACT_BROKER_URL

# Reset all provider states
curl -X POST http://localhost:8080/_pact/provider-states/reset

# Set up specific provider state
curl -X POST http://localhost:8080/_pact/provider-states \
  -H "Content-Type: application/json" \
  -d '{"state": "healthy patient data", "params": {}}'
```

## Troubleshooting

- **Service not starting**: Check AMR_RULES_PATH points to valid rules file
- **Tests failing**: Verify TESTING=true environment variable is set
- **Contract errors**: Check provider state data matches consumer expectations
- **Async timeouts**: Increase timeout values or check service performance

See `docs/PROVIDER_VERIFICATION_GUIDE.md` for comprehensive documentation.