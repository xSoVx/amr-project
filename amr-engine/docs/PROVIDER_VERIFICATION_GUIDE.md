# AMR Service Provider Verification Testing Guide

This comprehensive guide covers the complete provider verification testing framework for the AMR classification service, including database state setup, async scenario handling, webhook publishing, and CI pipeline integration.

## Overview

The provider verification testing framework ensures that the AMR classification service correctly implements all consumer contracts by:

- Loading consumer contracts from Pact broker
- Setting up database and rule engine states for each scenario
- Verifying response structure matches contract expectations
- Publishing verification results via webhooks
- Supporting both synchronous and asynchronous classification scenarios
- Providing CI/CD pipeline integration as a deployment gate

## Architecture

```
┌─────────────────────┐    ┌──────────────────────┐    ┌─────────────────────┐
│   Pact Broker       │    │  Provider Service    │    │  Verification       │
│                     │    │                      │    │  Tests              │
│ ┌─────────────────┐ │    │ ┌──────────────────┐ │    │ ┌─────────────────┐ │
│ │ Consumer        │ │───▶│ │ AMR Service      │ │◀───│ │ Test Framework  │ │
│ │ Contracts       │ │    │ │                  │ │    │ │                 │ │
│ └─────────────────┘ │    │ └──────────────────┘ │    │ └─────────────────┘ │
│                     │    │ ┌──────────────────┐ │    │ ┌─────────────────┐ │
│ ┌─────────────────┐ │    │ │ Provider State   │ │    │ │ Webhook         │ │
│ │ Verification    │ │◀───│ │ Endpoints        │ │    │ │ Publisher       │ │
│ │ Results         │ │    │ │                  │ │    │ │                 │ │
│ └─────────────────┘ │    │ └──────────────────┘ │    │ └─────────────────┘ │
└─────────────────────┘    └──────────────────────┘    └─────────────────────┘
          │                                                        │
          │                ┌──────────────────────┐                │
          └───────────────▶│   Database & Rule    │◀───────────────┘
                           │   Engine State       │
                           │   Manager            │
                           └──────────────────────┘
```

## Components

### 1. Provider Verification Test Framework

**File**: `tests/pact/test_provider_verification.py`

The main test framework that orchestrates provider verification:

- **TestProviderVerification**: Main test class with verification scenarios
- **ProviderVerificationFixture**: Test fixture for environment setup
- **Contract Loading**: Loads contracts from Pact broker or local files
- **Response Verification**: Validates API responses against contract expectations

#### Key Test Methods

```python
@pytest.mark.provider
@pytest.mark.asyncio
async def test_verify_consumer_contracts_from_broker():
    """Load and verify all consumer contracts from Pact broker."""
    
@pytest.mark.provider  
def test_verify_synchronous_classification():
    """Test synchronous classification endpoint verification."""
    
@pytest.mark.provider
@pytest.mark.asyncio
async def test_verify_asynchronous_classification():
    """Test asynchronous classification endpoint verification."""
```

### 2. Provider State Manager

**File**: `tests/pact/provider_state_manager.py`

Comprehensive state management for provider verification:

- **DatabaseState**: Manages patient, specimen, observation data
- **RuleEngineState**: Configures classification rules and profiles
- **AsyncTaskManager**: Handles async classification tasks
- **WebhookMocking**: Mocks external webhook endpoints

#### State Setup Methods

```python
def setup_provider_state(state_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Set up provider state for specific test scenario."""

async def async_state_context(state_name: str) -> AsyncGenerator[Dict[str, Any], None]:
    """Async context manager for provider state setup and cleanup."""
```

#### Supported Provider States

1. **healthy patient data** - Complete FHIR Bundle with valid AMR results
2. **healthy patient data for UI** - UI-specific test data
3. **invalid FHIR bundle** - Malformed bundle for error testing
4. **missing organism data** - Incomplete classification data
5. **HL7v2 message with missing MIC values** - Incomplete HL7v2 data
6. **invalid organism code data** - Unsupported organism codes
7. **IL-Core profile validation failure data** - Profile constraint violations
8. **mixed format batch data** - Batch requests with mixed formats

### 3. Async Scenario Handler

**File**: `tests/pact/async_scenarios.py`

Handles asynchronous classification scenarios:

- **AsyncTaskManager**: Manages async classification tasks
- **AsyncScenarioHandler**: High-level scenario execution
- **TaskStatus Tracking**: Monitors task lifecycle
- **Webhook Notifications**: Sends completion notifications

#### Async Scenarios

```python
async def run_scenario(scenario_name: str, scenario_params: Dict[str, Any]):
    """Run specific async classification scenario."""

# Supported scenarios:
# - happy_path: Successful async classification
# - missing_data: Classification with missing data
# - invalid_format: Invalid input format handling
# - timeout: Task expiration handling
# - webhook_notification: Completion webhook testing
# - batch_processing: Multiple async tasks
```

### 4. Webhook Publisher

**File**: `tests/pact/webhook_publisher.py`

Publishes verification results to multiple endpoints:

- **WebhookPublisher**: Main publisher class
- **VerificationResultCollector**: Accumulates test results
- **Multiple Handlers**: Pact broker, console, file, HTTP webhooks

#### Publishing Results

```python
async def publish_verification_results(
    report: ProviderVerificationReport,
    webhooks: List[str] = None
) -> Dict[str, Any]:
    """Publish verification results to configured webhooks."""
```

### 5. Provider State Endpoints

**File**: `amr_engine/api/pact_routes.py`

REST endpoints for provider state management:

- `POST /_pact/provider-states` - Set up provider state
- `DELETE /_pact/provider-states/{state}` - Clean up state
- `GET /_pact/provider-states` - List available states
- `POST /_pact/provider-states/reset` - Reset all states

## Running Provider Verification Tests

### Prerequisites

1. **Python 3.11+** and dependencies installed
2. **AMR service running** on configured port
3. **Pact broker available** (optional, can use local contracts)
4. **Database/Redis** configured for state persistence

### Environment Variables

```bash
# Required for provider verification
export TESTING=true
export PACT_VERIFICATION=true

# Pact broker configuration
export PACT_BROKER_URL=https://your-pact-broker.com
export PACT_BROKER_TOKEN=your-token
export PROVIDER_VERSION=1.0.0

# Service configuration
export AMR_RULES_PATH=amr_engine/rules/eucast_v_2025_1.yaml
export REDIS_ENABLED=true
export DATABASE_URL=postgresql://user:pass@localhost/amr_test
```

### Local Testing

#### Start AMR Service

```bash
# Start with provider state endpoints enabled
export TESTING=true
uvicorn amr_engine.main:app --host 0.0.0.0 --port 8080
```

#### Run Provider Verification Tests

```bash
# Run all provider verification tests
pytest tests/pact/test_provider_verification.py -v

# Run specific test scenarios
pytest tests/pact/test_provider_verification.py::TestProviderVerification::test_verify_synchronous_classification -v

# Run with specific consumer
pytest tests/pact/test_provider_verification.py --consumer-name=ui-service -v

# Run async scenario tests
pytest tests/pact/test_async_scenarios.py -v
```

#### Verify Against Pact Broker

```bash
# Verify all consumer contracts
pact-broker verify \
  --provider amr-classification-service \
  --provider-base-url http://localhost:8080 \
  --broker-base-url $PACT_BROKER_URL \
  --broker-token $PACT_BROKER_TOKEN \
  --provider-app-version $PROVIDER_VERSION \
  --publish-verification-results

# Verify specific consumer
pact-broker verify \
  --provider amr-classification-service \
  --provider-base-url http://localhost:8080 \
  --broker-base-url $PACT_BROKER_URL \
  --broker-token $PACT_BROKER_TOKEN \
  --consumer ui-service \
  --publish-verification-results
```

### CI/CD Pipeline Integration

The provider verification is integrated into GitHub Actions workflow:

**File**: `.github/workflows/pact-provider-verification.yml`

#### Pipeline Stages

1. **Provider Verification**
   - Matrix build for multiple consumers
   - Database and Redis services
   - AMR service startup
   - Contract verification
   - Async scenario testing

2. **Can I Deploy Check**
   - Deployment safety verification
   - All consumer-provider compatibility
   - Deployment gate creation

3. **Webhook Notifications**
   - External system notifications
   - Build status reporting

#### Deployment Gate

The pipeline creates a deployment gate that prevents deployment unless all contracts pass verification:

```yaml
can-i-deploy:
  name: Check deployment safety
  needs: provider-verification
  if: github.ref == 'refs/heads/main'
  
  steps:
  - name: Check if safe to deploy
    run: |
      pact-broker can-i-deploy \
        --pacticipant amr-consumer \
        --version $CONSUMER_VERSION \
        --pacticipant amr-classification-service \
        --version $PROVIDER_VERSION \
        --broker-base-url $PACT_BROKER_URL \
        --broker-token $PACT_BROKER_TOKEN
```

## Contract Scenarios Covered

### Synchronous Scenarios

1. **FHIR Bundle Classification**
   - Valid FHIR R4 bundles with complete AMR data
   - Multiple organism/antibiotic combinations
   - Profile validation (IL-Core, US-Core)

2. **HL7v2 Message Processing**
   - ORU^R01 messages with MIC/disc data
   - Auto-format detection
   - Content-Type header handling

3. **Direct JSON Input**
   - ClassificationInput objects
   - Validation and error handling
   - Multiple method support (MIC, DISC)

4. **Error Scenarios**
   - Invalid organism codes
   - Missing required data
   - Malformed input structures
   - RFC 7807 error responses

### Asynchronous Scenarios

1. **Task Creation**
   - Async classification initiation
   - Task ID generation
   - Status tracking

2. **Result Retrieval**
   - Polling for completion
   - Error handling
   - Result formatting

3. **Webhook Notifications**
   - Completion callbacks
   - Error notifications
   - Custom headers

4. **Batch Processing**
   - Multiple concurrent tasks
   - Resource management
   - Batch result aggregation

### Profile Validation Scenarios

1. **IL-Core Profile**
   - Hebrew name support
   - Israeli identifier requirements
   - Strict validation rules

2. **US-Core Profile**
   - US identifier standards
   - English name requirements
   - Flexible validation

## Database State Management

### Database Schema

The provider state manager creates in-memory SQLite tables:

```sql
CREATE TABLE patients (
    id TEXT PRIMARY KEY,
    mrn TEXT,
    name TEXT,
    gender TEXT,
    birth_date TEXT,
    active BOOLEAN DEFAULT TRUE,
    metadata TEXT
);

CREATE TABLE specimens (
    id TEXT PRIMARY KEY,
    patient_id TEXT,
    type TEXT,
    collected_date TEXT,
    status TEXT DEFAULT 'active',
    metadata TEXT
);

CREATE TABLE observations (
    id TEXT PRIMARY KEY,
    patient_id TEXT,
    specimen_id TEXT,
    organism TEXT,
    antibiotic TEXT,
    method TEXT,
    value REAL,
    unit TEXT,
    status TEXT DEFAULT 'final',
    metadata TEXT
);
```

### State Persistence

Provider states are persisted to support:

- **Test Isolation**: Each test gets clean state
- **State Cleanup**: Automatic cleanup after tests
- **Data Consistency**: Referential integrity maintained
- **Metadata Tracking**: Test scenario traceability

## Webhook Integration

### Supported Webhook Types

1. **Pact Broker**
   - Verification result publishing
   - Build URL linking
   - Tag management

2. **Console Output**
   - Formatted test results
   - Color-coded status
   - Summary statistics

3. **File Output**
   - JSON result files
   - Test artifacts
   - Timestamped reports

4. **HTTP Webhooks**
   - Custom endpoint notifications
   - Authentication support
   - Retry mechanisms

### Webhook Configuration

```python
# Configure webhook publishing
publisher = WebhookPublisher(pact_config)

# Publish to multiple endpoints
results = await publisher.publish_verification_results(
    report=verification_report,
    webhooks=["pact-broker", "console", "https://your-webhook.com"]
)
```

## Troubleshooting

### Common Issues

#### 1. Provider State Setup Failures

**Symptom**: Tests fail with "Unknown provider state" errors
**Solution**: 
- Check state names match exactly
- Verify provider_state_manager import
- Enable debug logging

```bash
pytest tests/pact/ -v -s --log-cli-level=DEBUG
```

#### 2. Contract Verification Failures

**Symptom**: Response doesn't match contract expectations
**Solution**:
- Compare actual vs expected response structure
- Check Pact matcher usage (Like, Term, EachLike)
- Verify provider state data accuracy

#### 3. Async Task Timeouts

**Symptom**: Async tests timeout waiting for completion
**Solution**:
- Increase timeout values in test configuration
- Check async task manager health
- Verify webhook endpoints are accessible

#### 4. Database Connection Issues

**Symptom**: Provider state setup fails with database errors
**Solution**:
- Check DATABASE_URL environment variable
- Verify database service is running
- Test connection manually

```python
from tests.pact.provider_state_manager import provider_state_manager
engine = provider_state_manager.db_engine
with engine.connect() as conn:
    result = conn.execute("SELECT 1")
    print(result.fetchone())
```

#### 5. CI/CD Pipeline Failures

**Symptom**: GitHub Actions workflow fails
**Solution**:
- Check environment variable configuration
- Verify service startup logs
- Test port availability

```bash
# Check if AMR service is running
curl -f http://localhost:8080/health

# Check provider state endpoint
curl -f http://localhost:8080/_pact/provider-states
```

### Debug Mode

Enable debug logging for detailed troubleshooting:

```bash
# Set debug environment
export LOG_LEVEL=DEBUG
export TESTING=true

# Run with debug output
pytest tests/pact/ -v -s --log-cli-level=DEBUG --tb=long
```

### Health Check Endpoints

The provider verification includes health check endpoints:

```bash
# Check overall health
curl http://localhost:8080/_pact/health

# List available provider states
curl http://localhost:8080/_pact/provider-states

# Check specific state information
curl http://localhost:8080/_pact/provider-states/healthy-patient-data
```

## Best Practices

### Test Organization

1. **Separate Concerns**: Keep consumer and provider tests separate
2. **State Isolation**: Each test should set up its own state
3. **Cleanup**: Always clean up resources after tests
4. **Naming**: Use descriptive test and state names

### Provider State Design

1. **Minimal Data**: Include only necessary data for each scenario
2. **Realistic Data**: Use realistic but not production data
3. **Edge Cases**: Cover boundary conditions and error scenarios
4. **Documentation**: Document state purpose and expected outcomes

### CI/CD Integration

1. **Fast Feedback**: Run provider verification early in pipeline
2. **Deployment Gates**: Block deployment on contract failures
3. **Notifications**: Send alerts for verification failures
4. **Artifact Storage**: Store test results and logs

### Monitoring and Alerting

1. **Health Checks**: Monitor provider verification endpoint health
2. **Performance**: Track verification execution time
3. **Success Rates**: Monitor contract compliance over time
4. **Failure Analysis**: Alert on repeated verification failures

## Future Enhancements

### Planned Features

1. **Contract Evolution Support**
   - Backward compatibility testing
   - Breaking change detection
   - Versioning strategies

2. **Enhanced Async Testing**
   - WebSocket support
   - Event streaming scenarios
   - Complex workflow testing

3. **Security Testing**
   - Authentication scenario validation
   - Authorization boundary testing
   - Security header verification

4. **Performance Testing**
   - Load testing integration
   - Response time validation
   - Concurrent user scenarios

## Resources

- [Pact Documentation](https://docs.pact.io/)
- [Contract Testing Best Practices](https://docs.pact.io/best_practices/)
- [FHIR R4 Specification](https://hl7.org/fhir/R4/)
- [HL7v2 Standards](https://www.hl7.org/implement/standards/)
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)

## Support

For questions or issues with provider verification testing:

1. Check this documentation first
2. Review test logs and error messages
3. Check GitHub Issues for similar problems
4. Create new issue with detailed reproduction steps

The provider verification framework ensures robust contract compliance and safe deployment practices for the AMR classification service.