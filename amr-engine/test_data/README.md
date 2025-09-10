# AMR Engine QA Test Data

This directory contains comprehensive test examples for Quality Assurance testing of the AMR Engine with pseudonymization functionality.

## 📁 Files Overview

### Test Examples
- `QA_TEST_EXAMPLES.md` - Complete documentation with all 20 test examples
- `hl7v2_good_example_1.txt` - Valid E. coli susceptibility report
- `hl7v2_good_example_2.txt` - Valid MRSA detection report  
- `hl7v2_bad_example_1.txt` - Invalid HL7v2 (missing MSH segment)
- `fhir_good_example_1.json` - Valid FHIR Bundle with E. coli data
- `fhir_bad_example_1.json` - Invalid FHIR (malformed JSON)

### Test Automation
- `run_qa_tests.sh` - Automated test runner script

## 🚀 Quick Start

### Prerequisites
1. AMR Engine container running on port 8090:
```bash
docker run -d -p 8090:8080 --name amr-engine-qa \
  -e PSEUDONYMIZATION_ENABLED=true \
  -e PSEUDONYM_SALT_KEY=qa_testing_salt_2024 \
  -e PSEUDONYM_DUMMY_ID_PREFIX=QA \
  amr-engine:hl7v2-final
```

### Run Individual Tests

#### HL7v2 Tests
```bash
# Good Example - Should return empty array [] with HTTP 200
curl -X POST "http://localhost:8090/classify/hl7v2" \
     -H "Content-Type: application/hl7-v2" \
     -d @hl7v2_good_example_1.txt

# Bad Example - Should return error with HTTP 400/500
curl -X POST "http://localhost:8090/classify/hl7v2" \
     -H "Content-Type: application/hl7-v2" \
     -d @hl7v2_bad_example_1.txt
```

#### FHIR Tests
```bash
# Good Example - Should process successfully
curl -X POST "http://localhost:8090/classify/fhir" \
     -H "Content-Type: application/fhir+json" \
     -d @fhir_good_example_1.json

# Bad Example - Should return parsing error
curl -X POST "http://localhost:8090/classify/fhir" \
     -H "Content-Type: application/fhir+json" \
     -d @fhir_bad_example_1.json
```

### Run All Tests
```bash
chmod +x run_qa_tests.sh
./run_qa_tests.sh
```

## 🔍 Expected Results

### Successful Processing
- **HTTP Status**: 200 OK
- **Response**: Empty array `[]` or classification results
- **Pseudonymization**: Original identifiers replaced with QA-prefixed pseudonyms
- **Logs**: Pseudonymization events logged successfully

### Error Cases
- **HTTP Status**: 400/500 (depending on error type)
- **Response**: Structured error message with details
- **Logs**: Error logged with diagnostic information

## 🎯 Test Categories

### HL7v2 Test Examples

#### Valid Cases (5 examples)
1. **Complete E. coli Report** - Full susceptibility testing with multiple antibiotics
2. **MRSA Detection** - Staphylococcus aureus with MRSA screening
3. **Klebsiella pneumoniae** - Multi-drug resistance testing
4. **Pseudomonas aeruginosa** - Wound culture with specialized antibiotics
5. **Enterococcus faecium** - VRE detection and testing

#### Invalid Cases (5 examples)
1. **Missing MSH Segment** - Critical structural error
2. **Malformed MSH** - Wrong field delimiters
3. **Missing OBX Segments** - Incomplete data
4. **Invalid Encoding** - Wrong separators throughout
5. **Truncated Message** - Incomplete transmission

### FHIR Test Examples

#### Valid Cases (5 examples)
1. **Complete Bundle** - Patient, Specimen, and Observations
2. **MRSA Detection Bundle** - Focused on resistance detection
3. **Multi-drug Testing** - Klebsiella with multiple antibiotics
4. **Individual Observation** - Single observation without bundle
5. **Batch Bundle** - Multiple patients in one bundle

#### Invalid Cases (5 examples)
1. **Invalid JSON** - Syntax errors in JSON structure
2. **Missing Required Fields** - FHIR validation failures
3. **Invalid Resource Type** - Non-existent FHIR resources
4. **Malformed References** - Broken resource references
5. **Empty/Null Values** - Missing critical data

## 🔒 Pseudonymization Verification

### Check for PHI Protection
```bash
# Look for pseudonymized identifiers in responses
curl -X POST "http://localhost:8090/classify/hl7v2" \
     -H "Content-Type: application/hl7-v2" \
     -d @hl7v2_good_example_1.txt | grep "QA-"

# Expected patterns:
# - QA-PT-XXXXXXXX (Patient IDs)
# - QA-MR-XXXXXXXX (MRN numbers) 
# - QA-SP-XXXXXXXX (Specimen IDs)
```

### Verify Logs
```bash
# Check Docker logs for pseudonymization activity
docker logs amr-engine-qa | grep "Pseudonymization"

# Expected log entries:
# - "Pseudonymization service initialized successfully"
# - "Pseudonymization event: ...success: true..."
```

## 📊 Test Results Tracking

### Success Criteria
- ✅ All valid examples process without errors
- ✅ All invalid examples return appropriate errors  
- ✅ Pseudonymization active for all valid requests
- ✅ No original PHI in responses or logs
- ✅ Consistent pseudonym generation
- ✅ Proper error handling and messages

### Performance Benchmarks
- ✅ Response time < 2 seconds for valid requests
- ✅ Memory usage remains stable
- ✅ No memory leaks during repeated testing
- ✅ Concurrent requests handled properly

## 🐛 Troubleshooting

### Common Issues

#### Container Not Available
```bash
# Check if container is running
docker ps | grep amr-engine-qa

# Restart if needed
docker stop amr-engine-qa && docker start amr-engine-qa
```

#### Port Conflicts
```bash
# Check what's using port 8090
netstat -tulpn | grep 8090

# Use different port if needed
docker run -d -p 8091:8080 --name amr-engine-qa-alt ...
```

#### Test File Not Found
```bash
# Ensure you're in the correct directory
ls -la test_data/

# Check file permissions
chmod 644 test_data/*.txt test_data/*.json
```

This comprehensive test suite ensures thorough validation of the AMR Engine pseudonymization system across multiple message formats and error conditions.