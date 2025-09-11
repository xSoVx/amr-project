"""
Pact consumer contract tests for /classify/fhir endpoint.

Tests the dedicated FHIR R4 processing endpoint that handles:
- FHIR R4 Bundles
- Arrays of FHIR Observation resources
- Single FHIR Observation resources
- Profile pack validation (IL-Core, US-Core, IPS, Base)

This ensures the consumer-provider contract is maintained for FHIR-specific processing.
"""

import pytest
import json
from typing import Dict, Any, List
from unittest.mock import patch

from pact import Consumer, Provider, Like, Term, EachLike
from requests import Session

from .provider_states import setup_provider_state


class TestClassifyFhirEndpointContract:
    """
    Pact contract tests for the /classify/fhir endpoint.
    
    Tests FHIR-specific processing and profile validation to ensure
    the API contract is maintained between consumer and provider.
    """
    
    @pytest.fixture(scope="class")
    def pact(self):
        """Initialize Pact consumer-provider relationship."""
        pact = Consumer("amr-fhir-consumer").has_pact_with(
            Provider("amr-classification-service"),
            host_name="localhost",
            port=8080,
            pact_dir="tests/pacts"
        )
        pact.start()
        yield pact
        pact.stop()
    
    def test_classify_fhir_with_bundle(self, pact):
        """
        Test /classify/fhir endpoint with FHIR Bundle.
        
        Provider state: healthy patient data
        Expected: Successful classification from FHIR Bundle
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
         .upon_receiving("a request to classify FHIR Bundle")
         .with_request(
             method="POST",
             path="/classify/fhir",
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
                f"{pact.uri}/classify/fhir",
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
                assert "method" in classification
    
    def test_classify_fhir_with_il_core_profile(self, pact):
        """
        Test /classify/fhir endpoint with IL-Core profile pack.
        
        Provider state: IL-Core patient data
        Expected: Successful classification with IL-Core validation
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
         .upon_receiving("a request to classify FHIR Bundle with IL-Core profile")
         .with_request(
             method="POST",
             path="/classify/fhir",
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
                f"{pact.uri}/classify/fhir",
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
                assert "ruleVersion" in classification
    
    def test_classify_fhir_with_us_core_profile_query_param(self, pact):
        """
        Test /classify/fhir endpoint with US-Core profile via query parameter.
        
        Provider state: US-Core patient data
        Expected: Successful classification with US-Core validation
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
         .upon_receiving("a request to classify FHIR Bundle with US-Core profile query")
         .with_request(
             method="POST",
             path="/classify/fhir",
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
                f"{pact.uri}/classify/fhir?profile_pack=US-Core",
                json=us_core_bundle,
                headers={"Content-Type": "application/json"}
            )
            
            assert response.status_code == 200
            result = response.json()
            assert len(result) >= 1
            for classification in result:
                assert classification["decision"] in ["S", "I", "R"]
    
    def test_classify_fhir_with_invalid_bundle(self, pact):
        """
        Test /classify/fhir endpoint with invalid FHIR Bundle.
        
        Provider state: invalid FHIR bundle
        Expected: 400 Bad Request with FHIR parsing error
        """
        invalid_bundle = setup_provider_state("invalid FHIR bundle")
        
        expected_error_response = {
            "type": Like("https://amr-engine.com/problems/fhir-parsing-error"),
            "title": Like("FHIR Parsing Error"),
            "status": Like(400),
            "detail": Term(r"FHIR parsing error:.*", "FHIR parsing error: Missing required elements"),
            "operationOutcome": {
                "resourceType": Like("OperationOutcome"),
                "issue": EachLike({
                    "severity": Like("error"),
                    "code": Like("invalid"),
                    "diagnostics": Term(r"FHIR parsing error:.*", "FHIR parsing error: Missing required elements")
                })
            }
        }
        
        (pact
         .given("invalid FHIR bundle")
         .upon_receiving("a request to classify invalid FHIR Bundle")
         .with_request(
             method="POST",
             path="/classify/fhir",
             headers={
                 "Content-Type": "application/json"
             },
             body=invalid_bundle
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
                f"{pact.uri}/classify/fhir",
                json=invalid_bundle,
                headers={"Content-Type": "application/json"}
            )
            
            assert response.status_code == 400
            result = response.json()
            assert result["type"].endswith("fhir-parsing-error")
            assert result["status"] == 400
            assert "FHIR parsing error" in result["detail"]
    
    def test_classify_fhir_with_missing_organism(self, pact):
        """
        Test /classify/fhir endpoint with missing organism data.
        
        Provider state: missing organism data
        Expected: 400 Bad Request due to missing organism information
        """
        missing_organism_bundle = setup_provider_state("missing organism data")
        
        expected_error_response = {
            "type": Like("https://amr-engine.com/problems/fhir-parsing-error"),
            "title": Like("FHIR Parsing Error"),
            "status": Like(400),
            "detail": Term(r".*organism.*", "FHIR parsing error: Missing organism information"),
            "operationOutcome": {
                "resourceType": Like("OperationOutcome"),
                "issue": EachLike({
                    "severity": Like("error"),
                    "code": Like("invalid"),
                    "diagnostics": Term(r".*organism.*", "FHIR parsing error: Missing organism information")
                })
            }
        }
        
        (pact
         .given("missing organism data")
         .upon_receiving("a request to classify FHIR Bundle with missing organism")
         .with_request(
             method="POST",
             path="/classify/fhir",
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
                f"{pact.uri}/classify/fhir",
                json=missing_organism_bundle,
                headers={"Content-Type": "application/json"}
            )
            
            assert response.status_code == 400
            result = response.json()
            assert result["status"] == 400
            assert "organism" in result["detail"].lower()
    
    def test_classify_fhir_with_single_observation(self, pact):
        """
        Test /classify/fhir endpoint with single FHIR Observation.
        
        Provider state: healthy patient data (extract single observation)
        Expected: Successful classification from single observation
        """
        # Extract single observation from healthy patient data
        healthy_bundle = setup_provider_state("healthy patient data")
        single_observation = None
        
        for entry in healthy_bundle["entry"]:
            if (entry["resource"]["resourceType"] == "Observation" and 
                "ampicillin" in entry["resource"]["id"].lower()):
                single_observation = entry["resource"]
                # Add organism component for completeness
                if "component" not in single_observation:
                    single_observation["component"] = []
                single_observation["component"].append({
                    "code": {
                        "coding": [
                            {
                                "system": "http://snomed.info/sct",
                                "code": "264395009",
                                "display": "Microorganism"
                            }
                        ]
                    },
                    "valueCodeableConcept": {
                        "coding": [
                            {
                                "system": "http://snomed.info/sct",
                                "code": "112283007",
                                "display": "Escherichia coli"
                            }
                        ]
                    }
                })
                break
        
        expected_response = EachLike({
            "specimenId": Term(r"^[a-zA-Z0-9-]+$", "ampicillin-mic"),
            "organism": Like("Escherichia coli"),
            "antibiotic": Like("Ampicillin"),
            "method": Like("MIC"),
            "input": {
                "organism": Like("Escherichia coli"),
                "antibiotic": Like("Ampicillin"),
                "method": Like("MIC"),
                "mic_mg_L": Like(16),
                "specimenId": Term(r"^[a-zA-Z0-9-]+$", "ampicillin-mic")
            },
            "decision": Term(r"^[SIR]$", "R"),
            "reason": Like("MIC 16 mg/L > breakpoint 8.0 mg/L"),
            "ruleVersion": Like("EUCAST v2025.1")
        })
        
        (pact
         .given("healthy patient data")
         .upon_receiving("a request to classify single FHIR Observation")
         .with_request(
             method="POST",
             path="/classify/fhir",
             headers={
                 "Content-Type": "application/json"
             },
             body=single_observation
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
                f"{pact.uri}/classify/fhir",
                json=single_observation,
                headers={"Content-Type": "application/json"}
            )
            
            assert response.status_code == 200
            result = response.json()
            assert len(result) >= 1
            for classification in result:
                assert classification["decision"] in ["S", "I", "R"]
    
    def test_classify_fhir_with_observation_array(self, pact):
        """
        Test /classify/fhir endpoint with array of FHIR Observations.
        
        Provider state: healthy patient data (extract observations)
        Expected: Successful classification from observation array
        """
        # Extract observations array from healthy patient data
        healthy_bundle = setup_provider_state("healthy patient data")
        observations = []
        
        for entry in healthy_bundle["entry"]:
            if entry["resource"]["resourceType"] == "Observation":
                obs = entry["resource"].copy()
                # Ensure organism component is present for antimicrobial observations
                if "ampicillin" in obs["id"].lower():
                    if "component" not in obs:
                        obs["component"] = []
                    obs["component"].append({
                        "code": {
                            "coding": [
                                {
                                    "system": "http://snomed.info/sct",
                                    "code": "264395009",
                                    "display": "Microorganism"
                                }
                            ]
                        },
                        "valueCodeableConcept": {
                            "coding": [
                                {
                                    "system": "http://snomed.info/sct",
                                    "code": "112283007",
                                    "display": "Escherichia coli"
                                }
                            ]
                        }
                    })
                    observations.append(obs)
        
        expected_response = EachLike({
            "specimenId": Term(r"^[a-zA-Z0-9-]+$", "ampicillin-mic"),
            "organism": Like("Escherichia coli"),
            "antibiotic": Like("Ampicillin"),
            "method": Like("MIC"),
            "input": {
                "organism": Like("Escherichia coli"),
                "antibiotic": Like("Ampicillin"),
                "method": Like("MIC"),
                "mic_mg_L": Like(16),
                "specimenId": Term(r"^[a-zA-Z0-9-]+$", "ampicillin-mic")
            },
            "decision": Term(r"^[SIR]$", "R"),
            "reason": Like("MIC 16 mg/L > breakpoint 8.0 mg/L"),
            "ruleVersion": Like("EUCAST v2025.1")
        })
        
        (pact
         .given("healthy patient data")
         .upon_receiving("a request to classify array of FHIR Observations")
         .with_request(
             method="POST",
             path="/classify/fhir",
             headers={
                 "Content-Type": "application/json"
             },
             body=observations
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
                f"{pact.uri}/classify/fhir",
                json=observations,
                headers={"Content-Type": "application/json"}
            )
            
            assert response.status_code == 200
            result = response.json()
            assert len(result) >= 1
            for classification in result:
                assert classification["decision"] in ["S", "I", "R"]
    
    def test_classify_fhir_with_malformed_json(self, pact):
        """
        Test /classify/fhir endpoint with malformed JSON.
        
        Provider state: none (test malformed JSON handling)
        Expected: 400 Bad Request with JSON parsing error
        """
        expected_error_response = {
            "type": Like("https://amr-engine.com/problems/json-parse-error"),
            "title": Like("JSON Parsing Error"),
            "status": Like(400),
            "detail": Term(r"Invalid JSON payload:.*", "Invalid JSON payload: malformed JSON")
        }
        
        (pact
         .upon_receiving("a request to classify FHIR with malformed JSON")
         .with_request(
             method="POST",
             path="/classify/fhir",
             headers={
                 "Content-Type": "application/json"
             },
             body="{ invalid json }"
         )
         .will_respond_with(
             status=400,
             headers={
                 "Content-Type": "application/json"
             },
             body=expected_error_response
         ))
        
        with pact:
            session = Session()
            response = session.post(
                f"{pact.uri}/classify/fhir",
                data="{ invalid json }",
                headers={"Content-Type": "application/json"}
            )
            
            assert response.status_code == 400
            result = response.json()
            assert result["type"].endswith("json-parse-error")
            assert result["status"] == 400