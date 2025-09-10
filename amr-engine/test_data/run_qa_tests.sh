#!/bin/bash

# AMR Engine QA Test Suite
# Tests the pseudonymization functionality with good and bad examples

BASE_URL="http://localhost:8090"
TEST_DIR="./test_data"

echo "🧪 AMR Engine QA Test Suite Starting..."
echo "Testing against: $BASE_URL"
echo "=================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

passed_tests=0
failed_tests=0

# Function to run a test
run_test() {
    local test_name="$1"
    local endpoint="$2"
    local content_type="$3"
    local data_file="$4"
    local expected_result="$5"
    
    echo -e "${YELLOW}Testing: $test_name${NC}"
    
    if [[ ! -f "$data_file" ]]; then
        echo -e "${RED}❌ Test file not found: $data_file${NC}"
        ((failed_tests++))
        return
    fi
    
    response=$(curl -s -w "%{http_code}" -X POST "$BASE_URL$endpoint" \
                   -H "Content-Type: $content_type" \
                   -d @"$data_file")
    
    http_code="${response: -3}"
    response_body="${response%???}"
    
    if [[ "$expected_result" == "success" ]]; then
        if [[ "$http_code" == "200" ]]; then
            echo -e "${GREEN}✅ PASS - HTTP $http_code${NC}"
            # Check for pseudonymization evidence
            if echo "$response_body" | grep -q "HL7-"; then
                echo -e "${GREEN}   ✅ Pseudonymization detected${NC}"
            else
                echo -e "${YELLOW}   ⚠️  No pseudonymization markers found${NC}"
            fi
            ((passed_tests++))
        else
            echo -e "${RED}❌ FAIL - Expected success but got HTTP $http_code${NC}"
            echo "   Response: $response_body"
            ((failed_tests++))
        fi
    else
        if [[ "$http_code" != "200" ]]; then
            echo -e "${GREEN}✅ PASS - Correctly failed with HTTP $http_code${NC}"
            ((passed_tests++))
        else
            echo -e "${RED}❌ FAIL - Expected failure but got HTTP $http_code${NC}"
            echo "   Response: $response_body"
            ((failed_tests++))
        fi
    fi
    echo ""
}

# Test container availability
echo "🔍 Checking if AMR Engine is available..."
if ! curl -s "$BASE_URL/health" > /dev/null; then
    echo -e "${RED}❌ AMR Engine not available at $BASE_URL${NC}"
    echo "Please start the container first:"
    echo "docker run -d -p 8090:8080 --name amr-engine-qa amr-engine:hl7v2-final"
    exit 1
fi
echo -e "${GREEN}✅ AMR Engine is available${NC}"
echo ""

# HL7v2 Good Examples
echo "📋 Testing HL7v2 Good Examples..."
run_test "HL7v2 Good Example 1 - E.coli Complete" "/classify/hl7v2" "application/hl7-v2" "$TEST_DIR/hl7v2_good_example_1.txt" "success"
run_test "HL7v2 Good Example 2 - MRSA Detection" "/classify/hl7v2" "text/plain" "$TEST_DIR/hl7v2_good_example_2.txt" "success"

# HL7v2 Bad Examples  
echo "📋 Testing HL7v2 Bad Examples..."
run_test "HL7v2 Bad Example 1 - Missing MSH" "/classify/hl7v2" "application/hl7-v2" "$TEST_DIR/hl7v2_bad_example_1.txt" "error"

# FHIR Good Examples
echo "📋 Testing FHIR Good Examples..."
run_test "FHIR Good Example 1 - Complete Bundle" "/classify/fhir" "application/fhir+json" "$TEST_DIR/fhir_good_example_1.json" "success"

# FHIR Bad Examples
echo "📋 Testing FHIR Bad Examples..."
run_test "FHIR Bad Example 1 - Invalid JSON" "/classify/fhir" "application/fhir+json" "$TEST_DIR/fhir_bad_example_1.json" "error"

# Test Summary
echo "=================================="
echo "🎯 Test Summary:"
echo -e "${GREEN}✅ Passed: $passed_tests${NC}"
echo -e "${RED}❌ Failed: $failed_tests${NC}"
echo -e "📊 Total: $((passed_tests + failed_tests))"

if [[ $failed_tests -eq 0 ]]; then
    echo -e "${GREEN}🎉 All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}💥 Some tests failed!${NC}"
    exit 1
fi