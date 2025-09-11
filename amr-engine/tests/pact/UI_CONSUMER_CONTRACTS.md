# UI Consumer Contracts for AMR Classification API

This document describes the Pact consumer contracts for the UI service consuming the AMR classification API. The contracts simulate various interaction scenarios including successful classifications, error conditions, and different input formats.

## Contract Overview

The UI consumer contracts (`test_ui_consumer_contract.py`) define five key interaction scenarios:

### 1. Successful FHIR Bundle Classification

**Scenario**: UI sends a valid FHIR Bundle with AMR test results  
**Expected**: Successful classification with S/I/R decision and metadata  

**Headers Required**:
- `Content-Type: application/fhir+json`
- `Authorization: Bearer ui-service-token-12345`
- `X-Correlation-ID: ui-correlation-001`

**Test Data**: Complete FHIR Bundle with Patient, Specimen, organism identification, and Ciprofloxacin MIC test results.

**Expected Response**: Classification result with decision "S" for susceptible, including organism, antibiotic, method, MIC value, and rule version.

### 2. HL7v2 Message with Missing MIC Values

**Scenario**: UI sends HL7v2 message with incomplete antimicrobial data  
**Expected**: Classification result indicating manual review required  

**Headers Required**:
- `Content-Type: application/hl7-v2`
- `Authorization: Bearer ui-service-token-12345`
- `X-Correlation-ID: ui-correlation-002`

**Test Data**: HL7v2 ORU^R01 message with Staphylococcus aureus organism but missing Vancomycin MIC value.

**Expected Response**: Classification with decision "Requires Review" and reason explaining missing MIC value.

### 3. Invalid Organism Code Error

**Scenario**: UI sends FHIR Bundle with invalid/unsupported organism code  
**Expected**: RFC 7807 Problem Details response with FHIR OperationOutcome  

**Headers Required**:
- `Content-Type: application/fhir+json`
- `Authorization: Bearer ui-service-token-12345`
- `X-Correlation-ID: ui-correlation-003`

**Test Data**: FHIR Bundle with invalid SNOMED CT organism code "999999999" (Unknown Alien Bacteria).

**Expected Response**: HTTP 400 with `application/problem+json` content type, including embedded FHIR OperationOutcome with error details.

### 4. IL-Core Profile Validation Failure

**Scenario**: UI sends FHIR Bundle that fails IL-Core profile validation  
**Expected**: Validation error with specific profile constraint details  

**Headers Required**:
- `Content-Type: application/fhir+json`
- `Authorization: Bearer ui-service-token-12345`
- `X-Correlation-ID: ui-correlation-004`
- `X-Profile-Pack: IL-Core`

**Test Data**: FHIR Bundle with Hebrew patient name but missing required IL-Core identifier.

**Expected Response**: HTTP 422 with profile validation error and OperationOutcome detailing IL-Core constraint violations.

### 5. Batch Classification with Mixed Formats

**Scenario**: UI sends batch request with both FHIR and direct JSON inputs  
**Expected**: Array of classification results for each input  

**Headers Required**:
- `Content-Type: application/json`
- `Authorization: Bearer ui-service-token-12345`
- `X-Correlation-ID: ui-correlation-005`

**Test Data**: Batch request containing:
- FHIR Observation with Ampicillin MIC test for E. coli
- Direct JSON input for Vancomycin MIC test for S. aureus

**Expected Response**: Array of classification results, each with appropriate decision and metadata.

## Provider States

The following provider states support the UI consumer contracts:

### New UI-Specific States

- **`healthy patient data for UI`** - Complete FHIR Bundle with UI-specific identifiers
- **`HL7v2 message with missing MIC values`** - HL7v2 message with incomplete antimicrobial data
- **`invalid organism code data`** - FHIR Bundle with unsupported organism code
- **`IL-Core profile validation failure data`** - FHIR Bundle that fails IL-Core validation
- **`mixed format batch data`** - Batch request with mixed input formats

## Running the Tests

### Prerequisites

1. **Python 3.11+** (required by project)
2. **Install dependencies**:
   ```bash
   pip install -e ".[dev]"
   ```

### Execute Tests

Run all UI consumer contract tests:
```bash
pytest tests/pact/test_ui_consumer_contract.py -v
```

Run specific test scenarios:
```bash
# Successful classification
pytest tests/pact/test_ui_consumer_contract.py::TestUIConsumerContracts::test_successful_fhir_bundle_classification -v

# Missing MIC scenario
pytest tests/pact/test_ui_consumer_contract.py::TestUIConsumerContracts::test_hl7v2_missing_mic_requires_review -v

# Invalid organism error
pytest tests/pact/test_ui_consumer_contract.py::TestUIConsumerContracts::test_invalid_organism_code_rfc7807_error -v

# Profile validation failure
pytest tests/pact/test_ui_consumer_contract.py::TestUIConsumerContracts::test_il_core_profile_validation_failure -v

# Batch processing
pytest tests/pact/test_ui_consumer_contract.py::TestUIConsumerContracts::test_batch_classification_mixed_formats -v
```

### Generated Contract Files

After running tests, the following Pact contract file is generated:
- `tests/pacts/ui-service-amr-classification-service.json`

## Contract Validation Features

### Headers Validation

All contracts validate the presence and format of required headers:
- **Authorization**: Bearer token authentication
- **X-Correlation-ID**: Request tracing identifier
- **Content-Type**: Appropriate MIME type for request format

### Response Format Validation

Contracts validate response structure using Pact matchers:
- **Like()**: Type matching for flexible values
- **Term()**: Regex validation for constrained values (e.g., S|I|R decisions)
- **EachLike()**: Array validation for batch responses

### Error Response Validation

Error scenarios validate RFC 7807 Problem Details format:
```json
{
  "type": "https://tools.ietf.org/html/rfc7807",
  "title": "Validation Error",
  "status": 400,
  "detail": "Error description",
  "operationOutcome": {
    "resourceType": "OperationOutcome",
    "issue": [...]
  }
}
```

## Integration with CI/CD

### Consumer Contract Publishing

Publish contracts to Pact broker:
```bash
pact-broker publish tests/pacts/*.json \
  --broker-base-url $PACT_BROKER_URL \
  --broker-token $PACT_BROKER_TOKEN \
  --consumer-app-version $UI_SERVICE_VERSION \
  --branch $GIT_BRANCH
```

### Provider Verification

The AMR classification service should verify these contracts:
```bash
pact-broker verify \
  --provider amr-classification-service \
  --provider-base-url http://localhost:8080 \
  --broker-base-url $PACT_BROKER_URL \
  --broker-token $PACT_BROKER_TOKEN
```

## Usage Examples

### Contract Test Structure

```python
@pytest.mark.pact
@pytest.mark.consumer
def test_successful_fhir_bundle_classification(self, ui_consumer_pact):
    # Define test data
    fhir_bundle = {...}
    expected_response = {...}
    
    # Set up Pact interaction
    (ui_consumer_pact
     .given("healthy patient data for UI")
     .upon_receiving("a request for FHIR Bundle classification from UI")
     .with_request(...)
     .will_respond_with(...))
    
    # Execute test
    with ui_consumer_pact:
        response = requests.post(...)
        assert response.status_code == 200
        assert response_data["decision"] in ["S", "I", "R"]
```

### Request/Response Patterns

**Successful Classification Request**:
```http
POST /classify/fhir HTTP/1.1
Content-Type: application/fhir+json
Authorization: Bearer ui-service-token-12345
X-Correlation-ID: ui-correlation-001

{FHIR Bundle}
```

**Successful Classification Response**:
```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "specimenId": "UI-SPEC001",
  "organism": "Escherichia coli",
  "antibiotic": "Ciprofloxacin",
  "method": "MIC",
  "decision": "S",
  "reason": "MIC 0.25 mg/L is <= breakpoint 0.5 mg/L",
  "ruleVersion": "EUCAST v2025.1"
}
```

## Benefits

### Contract-Driven Development

- **Early Integration Testing**: Catch API compatibility issues before deployment
- **Consumer-Driven**: UI requirements drive API contract specifications
- **Documentation**: Living documentation of API expectations

### Quality Assurance

- **Comprehensive Coverage**: Tests success, error, and edge cases
- **Header Validation**: Ensures proper authentication and tracing
- **Format Compliance**: Validates RFC 7807 error responses and FHIR standards

### Deployment Safety

- **Can-I-Deploy**: Safe deployment checks via Pact broker
- **Version Compatibility**: Track compatible consumer-provider versions
- **Regression Prevention**: Detect breaking changes automatically

## Maintenance

### Adding New Scenarios

1. **Create Provider State**: Add new state method to `provider_states.py`
2. **Add Test Method**: Create new test in `test_ui_consumer_contract.py`
3. **Update State Mapping**: Register new state in `setup_provider_state()`
4. **Run Tests**: Generate updated contract files

### Updating Existing Contracts

1. **Modify Test Data**: Update provider states for new data structures
2. **Update Expectations**: Adjust response matchers for new formats
3. **Regenerate**: Run tests to create updated contract files
4. **Verify**: Ensure provider still meets updated contracts

This comprehensive contract suite ensures reliable communication between the UI service and AMR classification API, providing confidence in system integration and API evolution.