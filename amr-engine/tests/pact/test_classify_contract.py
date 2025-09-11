"""
Pact consumer contract tests for /classify endpoint.

Tests the universal AMR classification endpoint that handles multiple input formats:
- Direct JSON ClassificationInput
- FHIR R4 Bundles and Observations
- HL7v2 messages

This ensures the consumer-provider contract is maintained across API changes.
"""

import pytest
import json
from typing import Dict, Any, List
from unittest.mock import patch

from pact import Consumer, Provider, Like, Term, EachLike
from requests import Session

from .provider_states import setup_provider_state


class TestClassifyEndpointContract:
    """
    Pact contract tests for the /classify endpoint.
    
    Tests various input formats and provider states to ensure
    the API contract is maintained between consumer and provider.
    """
    
    @pytest.fixture(scope="class")
    def pact(self):
        """Initialize Pact consumer-provider relationship."""
        pact = Consumer("amr-consumer").has_pact_with(
            Provider("amr-classification-service"),
            host_name="localhost",
            port=8080,
            pact_dir="tests/pacts"
        )
        pact.start()
        yield pact
        pact.stop()
    
    def test_classify_with_direct_json_input(self, pact):
        """
        Test /classify endpoint with direct JSON ClassificationInput.
        
        Provider state: direct classification input
        Expected: Successful classification with decision and reason
        """
        classification_input = setup_provider_state("direct classification input")
        
        expected_response = {
            "specimenId": Like("DIRECT-001"),
            "organism": Like("Escherichia coli"),
            "antibiotic": Like("Ciprofloxacin"),
            "method": Like("MIC"),
            "input": {
                "organism": Like("Escherichia coli"),
                "antibiotic": Like("Ciprofloxacin"),
                "method": Like("MIC"),
                "mic_mg_L": Like(0.25),
                "specimenId": Like("DIRECT-001")
            },
            "decision": Term(r"^[SIR]$", "S"),
            "reason": Like("MIC 0.25 mg/L <= breakpoint 0.5 mg/L"),
            "ruleVersion": Like("EUCAST v2025.1")
        }
        
        (pact
         .given("direct classification input")
         .upon_receiving("a request to classify AMR data with direct JSON input")
         .with_request(
             method="POST",
             path="/classify",
             headers={
                 "Content-Type": "application/json"
             },
             body=[classification_input]
         )
         .will_respond_with(
             status=200,
             headers={
                 "Content-Type": "application/json"
             },
             body=[expected_response]
         ))
        
        with pact:
            session = Session()
            response = session.post(
                f"{pact.uri}/classify",
                json=[classification_input],
                headers={"Content-Type": "application/json"}
            )
            
            assert response.status_code == 200
            result = response.json()
            assert len(result) == 1
            assert result[0]["decision"] in ["S", "I", "R"]
            assert "reason" in result[0]
            assert "ruleVersion" in result[0]
    
    def test_classify_with_fhir_bundle(self, pact):
        """
        Test /classify endpoint with FHIR Bundle input.
        
        Provider state: healthy patient data
        Expected: Successful classification from FHIR data
        """
        fhir_bundle = setup_provider_state("healthy patient data")
        
        expected_response = EachLike({
            "specimenId": Like("healthy-patient-bundle"),
            "organism": Like("Escherichia coli"),
            "antibiotic": Like("Ampicillin"),
            "method": Like("MIC"),
            "input": {
                "organism": Like("Escherichia coli"),
                "antibiotic": Like("Ampicillin"),
                "method": Like("MIC"),
                "mic_mg_L": Like(4.0),
                "specimenId": Like("healthy-patient-bundle")
            },
            "decision": Term(r"^[SIR]$", "S"),
            "reason": Like("MIC 4.0 mg/L <= breakpoint 8.0 mg/L"),
            "ruleVersion": Like("EUCAST v2025.1")
        })
        
        (pact
         .given("healthy patient data")
         .upon_receiving("a request to classify AMR data with FHIR Bundle")
         .with_request(
             method="POST",
             path="/classify",
             headers={
                 "Content-Type": "application/json"
             },
             body=fhir_bundle
         )
         .will_respond_with(
             status=200,
             headers={
                 "Content-Type": "application/json"
             },
             body=expected_response
         ))
        
        with pact:
            session = Session()
            response = session.post(
                f"{pact.uri}/classify",
                json=fhir_bundle,
                headers={"Content-Type": "application/json"}
            )
            
            assert response.status_code == 200
            result = response.json()
            assert len(result) >= 1
            for classification in result:
                assert classification["decision"] in ["S", "I", "R"]
                assert "organism" in classification
                assert "antibiotic" in classification
    
    def test_classify_with_hl7v2_message(self, pact):
        """
        Test /classify endpoint with HL7v2 message input.
        
        Provider state: healthy HL7v2 message
        Expected: Successful classification from HL7v2 data
        """
        hl7_message = setup_provider_state("healthy HL7v2 message")
        
        expected_response = EachLike({
            "specimenId": Term(r"^FINAL-SP-[A-Z0-9]+$", "FINAL-SP-ABC123"),
            "organism": Like("Staphylococcus aureus"),
            "antibiotic": Like("Oxacillin"),
            "method": Like("MIC"),
            "input": {
                "organism": Like("Staphylococcus aureus"),
                "antibiotic": Like("Oxacillin"),
                "method": Like("MIC"),
                "mic_mg_L": Like(1.0),
                "specimenId": Term(r"^FINAL-SP-[A-Z0-9]+$", "FINAL-SP-ABC123")
            },
            "decision": Term(r"^[SIR]$", "S"),
            "reason": Like("MIC 1.0 mg/L <= breakpoint 2.0 mg/L"),
            "ruleVersion": Like("EUCAST v2025.1")
        })
        
        (pact
         .given("healthy HL7v2 message")
         .upon_receiving("a request to classify AMR data with HL7v2 message")
         .with_request(
             method="POST",
             path="/classify",
             headers={
                 "Content-Type": "application/x-hl7-v2+er7"
             },
             body=hl7_message
         )
         .will_respond_with(
             status=200,
             headers={
                 "Content-Type": "application/json"
             },
             body=expected_response
         ))
        
        with pact:
            session = Session()
            response = session.post(
                f"{pact.uri}/classify",
                data=hl7_message,
                headers={"Content-Type": "application/x-hl7-v2+er7"}
            )
            
            assert response.status_code == 200
            result = response.json()
            assert len(result) >= 1
            for classification in result:
                assert classification["decision"] in ["S", "I", "R"]
                assert classification["specimenId"].startswith("FINAL-SP-")
    
    def test_classify_with_invalid_input(self, pact):
        """
        Test /classify endpoint with invalid input data.
        
        Provider state: invalid classification input
        Expected: 400 Bad Request with problem details
        """
        invalid_input = setup_provider_state("invalid classification input")
        
        expected_error_response = {
            "type": Like("https://amr-engine.com/problems/input-validation-error"),
            "title": Like("Input Validation Error"),
            "status": Like(400),
            "detail": Like("Missing required field: organism"),
            "operationOutcome": {
                "resourceType": Like("OperationOutcome"),
                "issue": EachLike({
                    "severity": Like("error"),
                    "code": Like("invalid"),
                    "diagnostics": Like("Missing required field: organism")
                })
            }
        }
        
        (pact
         .given("invalid classification input")
         .upon_receiving("a request to classify AMR data with invalid input")
         .with_request(
             method="POST",
             path="/classify",
             headers={
                 "Content-Type": "application/json"
             },
             body=[invalid_input]
         )
         .will_respond_with(
             status=400,
             headers={
                 "Content-Type": "application/problem+json"
             },
             body=expected_error_response
         ))
        
        with pact:
            session = Session()
            response = session.post(
                f"{pact.uri}/classify",
                json=[invalid_input],
                headers={"Content-Type": "application/json"}
            )
            
            assert response.status_code == 400
            result = response.json()
            assert result["type"].endswith("input-validation-error")
            assert result["status"] == 400
            assert "operationOutcome" in result
    
    def test_classify_with_fhir_profile_pack_header(self, pact):
        """
        Test /classify endpoint with FHIR profile pack selection via header.
        
        Provider state: IL-Core patient data
        Expected: Successful classification with IL-Core profile validation
        """
        il_core_bundle = setup_provider_state("IL-Core patient data")
        
        expected_response = EachLike({
            "specimenId": Like("il-core-patient-bundle"),
            "organism": Like("Escherichia coli"),
            "antibiotic": Like("Ampicillin"),
            "method": Like("MIC"),
            "input": {
                "organism": Like("Escherichia coli"),
                "antibiotic": Like("Ampicillin"),
                "method": Like("MIC"),
                "mic_mg_L": Like(2.0),
                "specimenId": Like("il-core-patient-bundle")
            },
            "decision": Term(r"^[SIR]$", "S"),
            "reason": Like("MIC 2.0 mg/L <= breakpoint 8.0 mg/L"),
            "ruleVersion": Like("EUCAST v2025.1")
        })
        
        (pact
         .given("IL-Core patient data")
         .upon_receiving("a request to classify AMR data with IL-Core profile pack")
         .with_request(
             method="POST",
             path="/classify",
             headers={
                 "Content-Type": "application/json",
                 "X-FHIR-Profile-Pack": "IL-Core"
             },
             body=il_core_bundle
         )
         .will_respond_with(
             status=200,
             headers={
                 "Content-Type": "application/json"
             },
             body=expected_response
         ))
        
        with pact:
            session = Session()
            response = session.post(
                f"{pact.uri}/classify",
                json=il_core_bundle,
                headers={
                    "Content-Type": "application/json",
                    "X-FHIR-Profile-Pack": "IL-Core"
                }
            )
            
            assert response.status_code == 200
            result = response.json()
            assert len(result) >= 1
            for classification in result:
                assert classification["decision"] in ["S", "I", "R"]
    
    def test_classify_with_fhir_profile_pack_query_param(self, pact):
        """
        Test /classify endpoint with FHIR profile pack selection via query parameter.
        
        Provider state: US-Core patient data
        Expected: Successful classification with US-Core profile validation
        """
        us_core_bundle = setup_provider_state("US-Core patient data")
        
        expected_response = EachLike({
            "specimenId": Like("us-core-patient-bundle"),
            "organism": Like("Klebsiella pneumoniae"),
            "antibiotic": Like("Cefotaxime"),
            "method": Like("MIC"),
            "input": {
                "organism": Like("Klebsiella pneumoniae"),
                "antibiotic": Like("Cefotaxime"),
                "method": Like("MIC"),
                "mic_mg_L": Like(0.5),
                "specimenId": Like("us-core-patient-bundle")
            },
            "decision": Term(r"^[SIR]$", "S"),
            "reason": Like("MIC 0.5 mg/L <= breakpoint 1.0 mg/L"),
            "ruleVersion": Like("EUCAST v2025.1")
        })
        
        (pact
         .given("US-Core patient data")
         .upon_receiving("a request to classify AMR data with US-Core profile pack")
         .with_request(
             method="POST",
             path="/classify",
             query="profile_pack=US-Core",
             headers={
                 "Content-Type": "application/json"
             },
             body=us_core_bundle
         )
         .will_respond_with(
             status=200,
             headers={
                 "Content-Type": "application/json"
             },
             body=expected_response
         ))
        
        with pact:
            session = Session()
            response = session.post(
                f"{pact.uri}/classify?profile_pack=US-Core",
                json=us_core_bundle,
                headers={"Content-Type": "application/json"}
            )
            
            assert response.status_code == 200
            result = response.json()
            assert len(result) >= 1
            for classification in result:
                assert classification["decision"] in ["S", "I", "R"]
    
    def test_classify_with_missing_organism_data(self, pact):
        """
        Test /classify endpoint with missing organism information.
        
        Provider state: missing organism data
        Expected: 400 Bad Request due to missing organism
        """
        missing_organism_bundle = setup_provider_state("missing organism data")
        
        expected_error_response = {
            "type": Like("https://amr-engine.com/problems/input-validation-error"),
            "title": Like("Input Validation Error"),
            "status": Like(400),
            "detail": Term(r".*organism.*", "Missing organism information"),
            "operationOutcome": {
                "resourceType": Like("OperationOutcome"),
                "issue": EachLike({
                    "severity": Like("error"),
                    "code": Like("invalid"),
                    "diagnostics": Term(r".*organism.*", "Missing organism information")
                })
            }
        }
        
        (pact
         .given("missing organism data")
         .upon_receiving("a request to classify AMR data with missing organism")
         .with_request(
             method="POST",
             path="/classify",
             headers={
                 "Content-Type": "application/json"
             },
             body=missing_organism_bundle
         )
         .will_respond_with(
             status=400,
             headers={
                 "Content-Type": "application/problem+json"
             },
             body=expected_error_response
         ))
        
        with pact:
            session = Session()
            response = session.post(
                f"{pact.uri}/classify",
                json=missing_organism_bundle,
                headers={"Content-Type": "application/json"}
            )
            
            assert response.status_code == 400
            result = response.json()
            assert result["status"] == 400
            assert "organism" in result["detail"].lower()