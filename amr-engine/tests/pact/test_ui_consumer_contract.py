"""
Pact consumer contracts for UI service consuming AMR classification API.

This module defines contract tests for the UI service consuming the AMR
classification API, simulating various interaction scenarios including
successful classifications, error conditions, and different input formats.
"""

import json
import pytest
import requests
from pact import Consumer, Provider, Like, Term, EachLike
from typing import Dict, Any


@pytest.fixture(scope="module")
def ui_consumer_pact(pact_dir):
    """
    Create Pact consumer for UI service testing.
    
    Args:
        pact_dir: Directory for storing Pact files
        
    Yields:
        Pact: Consumer-provider Pact instance for UI testing
    """
    pact = Consumer("ui-service").has_pact_with(
        Provider("amr-classification-service"),
        host_name="localhost",
        port=8083,  # Use different port to avoid conflicts
        pact_dir=str(pact_dir)
    )
    pact.start()
    yield pact
    pact.stop()


class TestUIConsumerContracts:
    """Test class for UI service consumer contracts."""

    @pytest.mark.pact
    @pytest.mark.consumer
    def test_successful_fhir_bundle_classification(self, ui_consumer_pact):
        """
        Test successful FHIR Bundle classification with S/I/R decision.
        
        Scenario: UI sends a valid FHIR Bundle with AMR test results
        Expected: Successful classification with decision and metadata
        """
        # FHIR Bundle input data
        fhir_bundle = {
            "resourceType": "Bundle",
            "id": "bundle-ecoli-ui-001",
            "type": "collection",
            "entry": [
                {
                    "resource": {
                        "resourceType": "Patient",
                        "id": "patient-ui-12345",
                        "identifier": [
                            {
                                "use": "usual",
                                "value": "UI-MRN12345678"
                            }
                        ],
                        "name": [
                            {
                                "family": "Smith",
                                "given": ["Jane", "A"]
                            }
                        ],
                        "gender": "female",
                        "birthDate": "1985-06-20"
                    }
                },
                {
                    "resource": {
                        "resourceType": "Specimen",
                        "id": "specimen-blood-ui-001",
                        "identifier": [
                            {
                                "value": "UI-SPEC001"
                            }
                        ],
                        "type": {
                            "coding": [
                                {
                                    "system": "http://snomed.info/sct",
                                    "code": "119297000",
                                    "display": "Blood specimen"
                                }
                            ]
                        },
                        "subject": {
                            "reference": "Patient/patient-ui-12345"
                        },
                        "collection": {
                            "collectedDateTime": "2024-09-11T10:30:00Z"
                        }
                    }
                },
                {
                    "resource": {
                        "resourceType": "Observation",
                        "id": "organism-ecoli-ui",
                        "status": "final",
                        "category": [
                            {
                                "coding": [
                                    {
                                        "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                                        "code": "laboratory"
                                    }
                                ]
                            }
                        ],
                        "code": {
                            "coding": [
                                {
                                    "system": "http://loinc.org",
                                    "code": "634-6",
                                    "display": "Bacteria identified in Specimen by Culture"
                                }
                            ]
                        },
                        "subject": {
                            "reference": "Patient/patient-ui-12345"
                        },
                        "specimen": {
                            "reference": "Specimen/specimen-blood-ui-001"
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
                    }
                },
                {
                    "resource": {
                        "resourceType": "Observation",
                        "id": "ciprofloxacin-mic-ui",
                        "status": "final",
                        "category": [
                            {
                                "coding": [
                                    {
                                        "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                                        "code": "laboratory"
                                    }
                                ]
                            }
                        ],
                        "code": {
                            "coding": [
                                {
                                    "system": "http://loinc.org",
                                    "code": "20629-2",
                                    "display": "Ciprofloxacin [Susceptibility] by Minimum inhibitory concentration (MIC)"
                                }
                            ]
                        },
                        "subject": {
                            "reference": "Patient/patient-ui-12345"
                        },
                        "specimen": {
                            "reference": "Specimen/specimen-blood-ui-001"
                        },
                        "valueQuantity": {
                            "value": 0.25,
                            "unit": "mg/L"
                        }
                    }
                }
            ]
        }

        expected_response = {
            "specimenId": Like("UI-SPEC001"),
            "organism": Like("Escherichia coli"),
            "antibiotic": Like("Ciprofloxacin"),
            "method": Like("MIC"),
            "input": {
                "organism": Like("Escherichia coli"),
                "antibiotic": Like("Ciprofloxacin"),
                "method": Like("MIC"),
                "mic_mg_L": Like(0.25),
                "specimenId": Like("UI-SPEC001")
            },
            "decision": Term(r"^[SIR]$", "S"),
            "reason": Like("MIC 0.25 mg/L is <= breakpoint 0.5 mg/L"),
            "ruleVersion": Like("EUCAST v2025.1")
        }

        (ui_consumer_pact
         .given("healthy patient data for UI")
         .upon_receiving("a request for FHIR Bundle classification from UI")
         .with_request(
             method="POST",
             path="/classify/fhir",
             headers={
                 "Content-Type": "application/fhir+json",
                 "Authorization": "Bearer ui-service-token-12345",
                 "X-Correlation-ID": "ui-correlation-001"
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

        with ui_consumer_pact:
            response = requests.post(
                f"http://localhost:8083/classify/fhir",
                json=fhir_bundle,
                headers={
                    "Content-Type": "application/fhir+json",
                    "Authorization": "Bearer ui-service-token-12345",
                    "X-Correlation-ID": "ui-correlation-001"
                }
            )

            assert response.status_code == 200
            response_data = response.json()
            assert response_data["decision"] in ["S", "I", "R"]
            assert "specimenId" in response_data
            assert "organism" in response_data
            assert "antibiotic" in response_data

    @pytest.mark.pact
    @pytest.mark.consumer
    def test_hl7v2_missing_mic_requires_review(self, ui_consumer_pact):
        """
        Test HL7v2 message processing with missing MIC values returning "Requires Review".
        
        Scenario: UI sends HL7v2 message with incomplete antimicrobial data
        Expected: Classification result indicating manual review required
        """
        hl7v2_message = (
            "MSH|^~\\&|UI_SYSTEM|UI_LAB|EMR|MAIN_HOSPITAL|20240911103000||ORU^R01|UI_MSG001|P|2.5\r"
            "PID|1||UI_P12345678^^^MRN^MR||JONES^MICHAEL^R||19750308|M|||456 ELM ST^^ANYTOWN^CA^90210||555-9876|||987654321\r"
            "OBR|1|||MICRO^Microbiology Culture^L||202409111000||||||||UI_SPEC002^BLOOD^L||||||||20240911103000|||F\r"
            "OBX|1|ST|ORG^Organism^L||Staphylococcus aureus||||||F\r"
            "OBX|2|ST|MIC^Vancomycin MIC^L||Missing|mg/L||||F\r"
        )

        expected_response = {
            "specimenId": Like("UI_SPEC002"),
            "organism": Like("Staphylococcus aureus"),
            "antibiotic": Like("Vancomycin"),
            "method": Like("MIC"),
            "input": {
                "organism": Like("Staphylococcus aureus"),
                "antibiotic": Like("Vancomycin"),
                "method": Like("MIC"),
                "specimenId": Like("UI_SPEC002")
            },
            "decision": Like("Requires Review"),
            "reason": Like("Missing MIC value - manual review required"),
            "ruleVersion": Like("EUCAST v2025.1")
        }

        (ui_consumer_pact
         .given("HL7v2 message with missing MIC values")
         .upon_receiving("a request for HL7v2 message processing with missing MIC")
         .with_request(
             method="POST",
             path="/classify/hl7v2",
             headers={
                 "Content-Type": "application/hl7-v2",
                 "Authorization": "Bearer ui-service-token-12345",
                 "X-Correlation-ID": "ui-correlation-002"
             },
             body=hl7v2_message
         )
         .will_respond_with(
             status=200,
             headers={
                 "Content-Type": "application/json"
             },
             body=expected_response
         ))

        with ui_consumer_pact:
            response = requests.post(
                f"http://localhost:8083/classify/hl7v2",
                data=hl7v2_message,
                headers={
                    "Content-Type": "application/hl7-v2",
                    "Authorization": "Bearer ui-service-token-12345",
                    "X-Correlation-ID": "ui-correlation-002"
                }
            )

            assert response.status_code == 200
            response_data = response.json()
            assert response_data["decision"] == "Requires Review"
            assert "Missing MIC value" in response_data["reason"]

    @pytest.mark.pact
    @pytest.mark.consumer
    def test_invalid_organism_code_rfc7807_error(self, ui_consumer_pact):
        """
        Test invalid organism code returning RFC 7807 error with embedded OperationOutcome.
        
        Scenario: UI sends FHIR Bundle with invalid/unsupported organism code
        Expected: RFC 7807 Problem Details response with FHIR OperationOutcome
        """
        invalid_fhir_bundle = {
            "resourceType": "Bundle",
            "id": "bundle-invalid-organism-ui",
            "type": "collection",
            "entry": [
                {
                    "resource": {
                        "resourceType": "Patient",
                        "id": "patient-ui-99999",
                        "identifier": [{"value": "UI-INVALID001"}],
                        "name": [{"family": "Test", "given": ["Invalid"]}]
                    }
                },
                {
                    "resource": {
                        "resourceType": "Specimen",
                        "id": "specimen-ui-invalid",
                        "identifier": [{"value": "UI-SPEC-INVALID"}],
                        "subject": {"reference": "Patient/patient-ui-99999"}
                    }
                },
                {
                    "resource": {
                        "resourceType": "Observation",
                        "id": "invalid-organism",
                        "status": "final",
                        "category": [
                            {
                                "coding": [
                                    {
                                        "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                                        "code": "laboratory"
                                    }
                                ]
                            }
                        ],
                        "code": {
                            "coding": [
                                {
                                    "system": "http://loinc.org",
                                    "code": "634-6",
                                    "display": "Bacteria identified in Specimen by Culture"
                                }
                            ]
                        },
                        "subject": {"reference": "Patient/patient-ui-99999"},
                        "specimen": {"reference": "Specimen/specimen-ui-invalid"},
                        "valueCodeableConcept": {
                            "coding": [
                                {
                                    "system": "http://snomed.info/sct",
                                    "code": "999999999",
                                    "display": "Unknown Alien Bacteria"
                                }
                            ]
                        }
                    }
                }
            ]
        }

        expected_error_response = {
            "type": Like("https://tools.ietf.org/html/rfc7807"),
            "title": Like("Validation Error"),
            "status": Like(400),
            "detail": Like("Invalid or unsupported organism code: 999999999"),
            "operationOutcome": {
                "resourceType": Like("OperationOutcome"),
                "issue": EachLike({
                    "severity": Like("error"),
                    "code": Like("invalid"),
                    "diagnostics": Like("Organism code '999999999' is not supported in AMR classification rules")
                })
            }
        }

        (ui_consumer_pact
         .given("invalid organism code data")
         .upon_receiving("a request with invalid organism code from UI")
         .with_request(
             method="POST",
             path="/classify/fhir",
             headers={
                 "Content-Type": "application/fhir+json",
                 "Authorization": "Bearer ui-service-token-12345",
                 "X-Correlation-ID": "ui-correlation-003"
             },
             body=invalid_fhir_bundle
         )
         .will_respond_with(
             status=400,
             headers={
                 "Content-Type": "application/problem+json"
             },
             body=expected_error_response
         ))

        with ui_consumer_pact:
            response = requests.post(
                f"http://localhost:8083/classify/fhir",
                json=invalid_fhir_bundle,
                headers={
                    "Content-Type": "application/fhir+json",
                    "Authorization": "Bearer ui-service-token-12345",
                    "X-Correlation-ID": "ui-correlation-003"
                }
            )

            assert response.status_code == 400
            assert response.headers.get("Content-Type") == "application/problem+json"
            response_data = response.json()
            assert "operationOutcome" in response_data
            assert response_data["operationOutcome"]["resourceType"] == "OperationOutcome"

    @pytest.mark.pact
    @pytest.mark.consumer
    def test_il_core_profile_validation_failure(self, ui_consumer_pact):
        """
        Test profile pack validation failure for IL-Core constraints.
        
        Scenario: UI sends FHIR Bundle that fails IL-Core profile validation
        Expected: Validation error with specific profile constraint details
        """
        il_core_bundle = {
            "resourceType": "Bundle",
            "id": "bundle-il-core-fail",
            "type": "collection",
            "entry": [
                {
                    "resource": {
                        "resourceType": "Patient",
                        "id": "patient-il-fail",
                        # Missing required IL-Core identifier
                        "name": [{"family": "כהן", "given": ["דוד"]}],
                        "gender": "male"
                    }
                },
                {
                    "resource": {
                        "resourceType": "Specimen",
                        "id": "specimen-il-fail",
                        "subject": {"reference": "Patient/patient-il-fail"}
                        # Missing required IL-Core specimen details
                    }
                }
            ]
        }

        expected_error_response = {
            "type": Like("https://tools.ietf.org/html/rfc7807"),
            "title": Like("Profile Validation Error"),
            "status": Like(422),
            "detail": Like("FHIR resource does not conform to IL-Core profile constraints"),
            "operationOutcome": {
                "resourceType": Like("OperationOutcome"),
                "issue": EachLike({
                    "severity": Like("error"),
                    "code": Like("structure"),
                    "diagnostics": Like("Patient resource is missing required IL-Core identifier")
                })
            }
        }

        (ui_consumer_pact
         .given("IL-Core profile validation failure data")
         .upon_receiving("a request with IL-Core profile validation failure")
         .with_request(
             method="POST",
             path="/classify/fhir",
             headers={
                 "Content-Type": "application/fhir+json",
                 "Authorization": "Bearer ui-service-token-12345",
                 "X-Correlation-ID": "ui-correlation-004",
                 "X-Profile-Pack": "IL-Core"
             },
             body=il_core_bundle
         )
         .will_respond_with(
             status=422,
             headers={
                 "Content-Type": "application/problem+json"
             },
             body=expected_error_response
         ))

        with ui_consumer_pact:
            response = requests.post(
                f"http://localhost:8083/classify/fhir",
                json=il_core_bundle,
                headers={
                    "Content-Type": "application/fhir+json",
                    "Authorization": "Bearer ui-service-token-12345",
                    "X-Correlation-ID": "ui-correlation-004",
                    "X-Profile-Pack": "IL-Core"
                }
            )

            assert response.status_code == 422
            response_data = response.json()
            assert "IL-Core" in response_data["detail"]
            assert response_data["operationOutcome"]["resourceType"] == "OperationOutcome"

    @pytest.mark.pact
    @pytest.mark.consumer
    def test_batch_classification_mixed_formats(self, ui_consumer_pact):
        """
        Test batch classification request with mixed input formats.
        
        Scenario: UI sends batch request with both FHIR and direct JSON inputs
        Expected: Array of classification results for each input
        """
        batch_request = {
            "requests": [
                {
                    "type": "fhir",
                    "data": {
                        "resourceType": "Observation",
                        "id": "batch-obs-1",
                        "status": "final",
                        "category": [
                            {
                                "coding": [
                                    {
                                        "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                                        "code": "laboratory"
                                    }
                                ]
                            }
                        ],
                        "code": {
                            "coding": [
                                {
                                    "system": "http://loinc.org",
                                    "code": "18864-9",
                                    "display": "Ampicillin [Susceptibility] by Minimum inhibitory concentration (MIC)"
                                }
                            ]
                        },
                        "valueQuantity": {
                            "value": 8,
                            "unit": "mg/L"
                        },
                        "component": [
                            {
                                "code": {
                                    "coding": [
                                        {
                                            "system": "http://loinc.org",
                                            "code": "634-6",
                                            "display": "Bacteria identified"
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
                            }
                        ]
                    }
                },
                {
                    "type": "direct",
                    "data": {
                        "organism": "Staphylococcus aureus",
                        "antibiotic": "Vancomycin",
                        "method": "MIC",
                        "mic_mg_L": 2.0,
                        "specimenId": "UI-BATCH-002"
                    }
                }
            ]
        }

        expected_response = EachLike({
            "specimenId": Like("UI-BATCH-001"),
            "organism": Like("Escherichia coli"),
            "antibiotic": Like("Ampicillin"),
            "method": Like("MIC"),
            "input": {
                "organism": Like("Escherichia coli"),
                "antibiotic": Like("Ampicillin"),
                "method": Like("MIC"),
                "mic_mg_L": Like(8.0)
            },
            "decision": Term(r"^[SIR]$", "I"),
            "reason": Like("MIC 8.0 mg/L is within intermediate range"),
            "ruleVersion": Like("EUCAST v2025.1")
        })

        (ui_consumer_pact
         .given("mixed format batch data")
         .upon_receiving("a batch classification request with mixed formats")
         .with_request(
             method="POST",
             path="/classify/batch",
             headers={
                 "Content-Type": "application/json",
                 "Authorization": "Bearer ui-service-token-12345",
                 "X-Correlation-ID": "ui-correlation-005"
             },
             body=batch_request
         )
         .will_respond_with(
             status=200,
             headers={
                 "Content-Type": "application/json"
             },
             body=expected_response
         ))

        with ui_consumer_pact:
            response = requests.post(
                f"http://localhost:8083/classify/batch",
                json=batch_request,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer ui-service-token-12345",
                    "X-Correlation-ID": "ui-correlation-005"
                }
            )

            assert response.status_code == 200
            response_data = response.json()
            assert isinstance(response_data, list)
            assert len(response_data) >= 1
            for result in response_data:
                assert "decision" in result
                assert result["decision"] in ["S", "I", "R"]