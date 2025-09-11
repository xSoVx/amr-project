# Pact Contract Testing for AMR Classification Service

This directory contains Pact consumer contract tests for the AMR classification microservice. These tests ensure API compatibility between consumers and the AMR classification provider service.

## Overview

The Pact contract tests cover three main endpoints:

- `/classify` - Universal AMR classification endpoint (handles FHIR, HL7v2, and direct JSON)
- `/classify/fhir` - Dedicated FHIR R4 processing endpoint
- `/classify/hl7v2` - Dedicated HL7v2 message processing endpoint

## Test Structure

```
tests/pact/
├── __init__.py                      # Package initialization
├── conftest.py                      # Pytest configuration and fixtures
├── provider_states.py              # Provider state management
├── test_classify_contract.py        # /classify endpoint contracts
├── test_classify_fhir_contract.py   # /classify/fhir endpoint contracts
├── test_classify_hl7v2_contract.py  # /classify/hl7v2 endpoint contracts
├── pact_config.py                   # Pact broker configuration
└── README.md                        # This file
```

## Provider States

The following provider states are defined for testing different scenarios:

### Data States
- **healthy patient data** - Complete, valid FHIR Bundle with AMR test results
- **invalid FHIR bundle** - Malformed FHIR Bundle for error testing
- **missing organism data** - Data missing required organism information
- **IL-Core patient data** - Israeli healthcare standard compliant data
- **US-Core patient data** - US healthcare interoperability standard compliant data

### HL7v2 States
- **healthy HL7v2 message** - Well-formed HL7v2 message with AMR data
- **malformed HL7v2 message** - Invalid HL7v2 message for error testing

### Direct Input States
- **direct classification input** - Valid ClassificationInput JSON object
- **invalid classification input** - Invalid input missing required fields

## Running Tests

### Prerequisites

1. Install dependencies:
```bash
pip install -e ".[dev]"
```

2. Ensure the AMR service is configured properly:
```bash
export AMR_RULES_PATH=amr_engine/rules/eucast_v_2025_1.yaml
export LOG_LEVEL=INFO
export REDIS_ENABLED=false
```

### Run Consumer Tests

Run all Pact contract tests:
```bash
pytest tests/pact/ -v
```

Run specific endpoint tests:
```bash
# Universal classify endpoint
pytest tests/pact/test_classify_contract.py -v

# FHIR endpoint
pytest tests/pact/test_classify_fhir_contract.py -v

# HL7v2 endpoint
pytest tests/pact/test_classify_hl7v2_contract.py -v
```

Run with specific markers:
```bash
# Run only consumer tests
pytest tests/pact/ -m consumer -v

# Run only Pact tests
pytest tests/pact/ -m pact -v
```

### Generated Pact Files

After running tests, Pact contract files are generated in `tests/pacts/`:

- `amr-consumer-amr-classification-service.json`
- `amr-fhir-consumer-amr-classification-service.json`
- `amr-hl7v2-consumer-amr-classification-service.json`

## Pact Broker Integration

### Environment Variables

Configure the following environment variables for Pact broker integration:

```bash
# Required
export PACT_BROKER_URL=https://your-pact-broker.com

# Authentication (choose one)
export PACT_BROKER_TOKEN=your-bearer-token
# OR
export PACT_BROKER_USERNAME=username
export PACT_BROKER_PASSWORD=password

# Version information
export PACT_CONSUMER_VERSION=1.0.0
export PACT_PROVIDER_VERSION=1.0.0

# Optional
export GIT_BRANCH=main
export BUILD_URL=https://ci.example.com/builds/123
export PACT_TAGS=main,latest
```

### Publishing Contracts

Publish consumer contracts to the Pact broker:

```python
from tests.pact.pact_config import get_pact_publish_command
import subprocess

# Generate and run publish command
cmd = get_pact_publish_command()
subprocess.run(cmd, shell=True, check=True)
```

Or use the CLI directly:
```bash
pact-broker publish tests/pacts/*.json \
  --broker-base-url $PACT_BROKER_URL \
  --broker-token $PACT_BROKER_TOKEN \
  --consumer-app-version $PACT_CONSUMER_VERSION \
  --branch $GIT_BRANCH
```

### Provider Verification

Verify provider against published contracts:

```bash
# Start the AMR service
uvicorn amr_engine.main:app --host 0.0.0.0 --port 8080 &

# Run provider verification
pact-broker verify \
  --provider amr-classification-service \
  --provider-base-url http://localhost:8080 \
  --broker-base-url $PACT_BROKER_URL \
  --broker-token $PACT_BROKER_TOKEN \
  --provider-app-version $PACT_PROVIDER_VERSION \
  --publish-verification-results
```

### Deployment Safety Check

Check if it's safe to deploy:

```bash
pact-broker can-i-deploy \
  --pacticipant amr-consumer \
  --version $PACT_CONSUMER_VERSION \
  --pacticipant amr-classification-service \
  --version $PACT_PROVIDER_VERSION \
  --broker-base-url $PACT_BROKER_URL \
  --broker-token $PACT_BROKER_TOKEN
```

## CI/CD Integration

### GitHub Actions

Use the generated GitHub Actions workflow:

```yaml
# Copy from pact_config.create_github_actions_workflow()
```

### GitLab CI

Use the generated GitLab CI pipeline:

```yaml
# Copy from pact_config.create_gitlab_ci_pipeline()
```

### Jenkins

Use the generated Jenkins pipeline:

```groovy
// Copy from pact_config.create_jenkins_pipeline()
```

## Local Pact Broker Setup

For local development, you can run a Pact broker using Docker Compose:

```bash
# Save the Docker Compose configuration
python -c "
from tests.pact.pact_config import create_docker_compose_pact_broker
with open('docker-compose.pact-broker.yml', 'w') as f:
    f.write(create_docker_compose_pact_broker())
"

# Start the Pact broker
docker-compose -f docker-compose.pact-broker.yml up -d

# Access the broker at http://localhost:9292
# Default credentials: admin/admin
```

## Test Scenarios Covered

### /classify Endpoint

1. **Direct JSON Input**
   - Valid ClassificationInput object
   - Invalid input with missing fields
   - Multiple classification inputs

2. **FHIR Bundle Processing**
   - Complete FHIR Bundle with Patient, Specimen, Observations
   - IL-Core profile pack validation (via header)
   - US-Core profile pack validation (via query parameter)
   - Invalid FHIR Bundle handling
   - Missing organism data handling

3. **HL7v2 Message Processing**
   - Standard HL7v2 ORU^R01 messages
   - Auto-detection of HL7v2 format
   - Content-Type header handling

### /classify/fhir Endpoint

1. **FHIR Bundle Processing**
   - Complete FHIR Bundle
   - Single FHIR Observation
   - Array of FHIR Observations

2. **Profile Pack Validation**
   - IL-Core profiles with Hebrew names
   - US-Core profiles with US-specific elements
   - Query parameter vs header priority

3. **Error Handling**
   - Invalid FHIR Bundle structure
   - Missing organism information
   - Malformed JSON input

### /classify/hl7v2 Endpoint

1. **Message Processing**
   - Standard HL7v2 messages with MIC data
   - Disc diffusion test data
   - Multiple organisms in single message

2. **Content-Type Support**
   - application/hl7-v2
   - text/plain
   - application/x-hl7

3. **Error Handling**
   - Malformed HL7v2 messages
   - Missing MSH segment
   - Empty message body

## Expected Responses

All successful classification responses include:

```json
{
  "specimenId": "string",
  "organism": "string",
  "antibiotic": "string", 
  "method": "MIC|DISC",
  "input": {
    "organism": "string",
    "antibiotic": "string",
    "method": "MIC|DISC",
    "mic_mg_L": "number (for MIC)",
    "disc_zone_mm": "number (for DISC)",
    "specimenId": "string"
  },
  "decision": "S|I|R",
  "reason": "string",
  "ruleVersion": "string"
}
```

Error responses follow RFC 7807 Problem Details format:

```json
{
  "type": "string",
  "title": "string",
  "status": "number",
  "detail": "string",
  "operationOutcome": {
    "resourceType": "OperationOutcome",
    "issue": [
      {
        "severity": "error",
        "code": "invalid",
        "diagnostics": "string"
      }
    ]
  }
}
```

## Maintenance

### Adding New Test Scenarios

1. **Add Provider State**
   - Update `provider_states.py` with new state method
   - Add state to `setup_provider_state()` mapping

2. **Create Contract Test**
   - Add test method to appropriate contract test file
   - Use `.given()` with new provider state
   - Define expected request and response

3. **Update Documentation**
   - Add scenario to this README
   - Update provider state list

### Updating Existing Contracts

1. **Modify Provider State Data**
   - Update provider state methods to reflect new data structure
   - Ensure backward compatibility if possible

2. **Update Contract Expectations**
   - Modify expected response structures
   - Update request body formats
   - Adjust matchers as needed

3. **Regenerate Contracts**
   - Run tests to generate new contract files
   - Publish updated contracts to broker
   - Verify provider compliance

## Troubleshooting

### Common Issues

1. **Pact Mock Service Port Conflicts**
   ```bash
   # Use different ports for concurrent test runs
   export PACT_MOCK_SERVICE_PORT=8081
   pytest tests/pact/test_classify_contract.py
   ```

2. **Provider State Setup Failures**
   ```bash
   # Check provider state data validity
   python -c "
   from tests.pact.provider_states import setup_provider_state
   print(setup_provider_state('healthy patient data'))
   "
   ```

3. **Contract Publishing Failures**
   ```bash
   # Verify broker connectivity
   curl -f $PACT_BROKER_URL/diagnostic/status/heartbeat
   
   # Check authentication
   pact-broker list-pacticipants \
     --broker-base-url $PACT_BROKER_URL \
     --broker-token $PACT_BROKER_TOKEN
   ```

4. **Provider Verification Failures**
   ```bash
   # Ensure provider is running
   curl -f http://localhost:8080/health
   
   # Check provider state endpoint
   curl -f http://localhost:8080/_pact/provider-states
   ```

### Debug Mode

Run tests with debug logging:

```bash
pytest tests/pact/ -v -s --log-cli-level=DEBUG
```

### Contract File Inspection

Examine generated contract files:

```bash
cat tests/pacts/amr-consumer-amr-classification-service.json | jq '.'
```

## Resources

- [Pact Documentation](https://docs.pact.io/)
- [Pact Python](https://github.com/pact-foundation/pact-python)
- [Contract Testing Best Practices](https://docs.pact.io/best_practices/)
- [FHIR R4 Specification](https://hl7.org/fhir/R4/)
- [HL7v2 Standard](https://www.hl7.org/implement/standards/product_brief.cfm?product_id=185)