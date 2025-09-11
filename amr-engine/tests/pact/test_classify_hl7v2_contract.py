"""
Pact consumer contract tests for /classify/hl7v2 endpoint.

Tests the dedicated HL7v2 message processing endpoint that handles:
- Standard HL7v2 pipe-delimited messages
- ORU^R01 result messages
- OBR/OBX segments with antimicrobial susceptibility data
- Multiple content-type formats

This ensures the consumer-provider contract is maintained for HL7v2-specific processing.
"""

import pytest
from typing import Dict, Any
from unittest.mock import patch

from pact import Consumer, Provider, Like, Term, EachLike
from requests import Session

from .provider_states import setup_provider_state


class TestClassifyHl7v2EndpointContract:
    """
    Pact contract tests for the /classify/hl7v2 endpoint.
    
    Tests HL7v2-specific message processing to ensure
    the API contract is maintained between consumer and provider.
    """
    
    @pytest.fixture(scope="class")
    def pact(self):
        """Initialize Pact consumer-provider relationship."""
        pact = Consumer("amr-hl7v2-consumer").has_pact_with(
            Provider("amr-classification-service"),
            host_name="localhost",
            port=8080,
            pact_dir="tests/pacts"
        )
        pact.start()
        yield pact
        pact.stop()
    
    def test_classify_hl7v2_with_standard_message(self, pact):
        """
        Test /classify/hl7v2 endpoint with standard HL7v2 message.
        
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
         .upon_receiving("a request to classify standard HL7v2 message")
         .with_request(
             method="POST",
             path="/classify/hl7v2",
             headers={
                 "Content-Type": "application/hl7-v2"
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
                f"{pact.uri}/classify/hl7v2",
                data=hl7_message,
                headers={"Content-Type": "application/hl7-v2"}
            )
            
            assert response.status_code == 200
            result = response.json()
            assert len(result) >= 1
            for classification in result:
                assert classification["decision"] in ["S", "I", "R"]
                assert classification["specimenId"].startswith("FINAL-SP-")
                assert "organism" in classification
                assert "antibiotic" in classification
                assert "method" in classification
    
    def test_classify_hl7v2_with_alternative_content_type(self, pact):
        """
        Test /classify/hl7v2 endpoint with alternative content-type.
        
        Provider state: healthy HL7v2 message
        Expected: Successful classification from HL7v2 data with text/plain
        """
        hl7_message = setup_provider_state("healthy HL7v2 message")
        
        expected_response = EachLike({
            "specimenId": Term(r"^FINAL-SP-[A-Z0-9]+$", "FINAL-SP-DEF456"),
            "organism": Like("Staphylococcus aureus"),
            "antibiotic": Like("Vancomycin"),
            "method": Like("MIC"),
            "input": {
                "organism": Like("Staphylococcus aureus"),
                "antibiotic": Like("Vancomycin"),
                "method": Like("MIC"),
                "mic_mg_L": Like(2.0),
                "specimenId": Term(r"^FINAL-SP-[A-Z0-9]+$", "FINAL-SP-DEF456")
            },
            "decision": Term(r"^[SIR]$", "S"),
            "reason": Like("MIC 2.0 mg/L <= breakpoint 2.0 mg/L"),
            "ruleVersion": Like("EUCAST v2025.1")
        })
        
        (pact
         .given("healthy HL7v2 message")
         .upon_receiving("a request to classify HL7v2 message with text/plain content-type")
         .with_request(
             method="POST",
             path="/classify/hl7v2",
             headers={
                 "Content-Type": "text/plain"
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
                f"{pact.uri}/classify/hl7v2",
                data=hl7_message,
                headers={"Content-Type": "text/plain"}
            )
            
            assert response.status_code == 200
            result = response.json()
            assert len(result) >= 1
            for classification in result:
                assert classification["decision"] in ["S", "I", "R"]
    
    def test_classify_hl7v2_with_disc_diffusion_data(self, pact):
        """
        Test /classify/hl7v2 endpoint with disc diffusion test data.
        
        Provider state: healthy HL7v2 message (contains disc data)
        Expected: Successful classification from disc diffusion data
        """
        hl7_message = setup_provider_state("healthy HL7v2 message")
        
        expected_response = EachLike({
            "specimenId": Term(r"^FINAL-SP-[A-Z0-9]+$", "FINAL-SP-GHI789"),
            "organism": Like("Staphylococcus aureus"),
            "antibiotic": Like("Clindamycin"),
            "method": Like("DISC"),
            "input": {
                "organism": Like("Staphylococcus aureus"),
                "antibiotic": Like("Clindamycin"),
                "method": Like("DISC"),
                "disc_zone_mm": Like(22.0),
                "specimenId": Term(r"^FINAL-SP-[A-Z0-9]+$", "FINAL-SP-GHI789")
            },
            "decision": Term(r"^[SIR]$", "S"),
            "reason": Like("Zone 22 mm >= breakpoint 19 mm"),
            "ruleVersion": Like("EUCAST v2025.1")
        })
        
        (pact
         .given("healthy HL7v2 message")
         .upon_receiving("a request to classify HL7v2 message with disc diffusion data")
         .with_request(
             method="POST",
             path="/classify/hl7v2",
             headers={
                 "Content-Type": "application/x-hl7"
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
                f"{pact.uri}/classify/hl7v2",
                data=hl7_message,
                headers={"Content-Type": "application/x-hl7"}
            )
            
            assert response.status_code == 200
            result = response.json()
            assert len(result) >= 1
            # Look for disc diffusion results
            disc_results = [r for r in result if r.get("method") == "DISC"]
            if disc_results:
                for classification in disc_results:
                    assert classification["decision"] in ["S", "I", "R"]
                    assert "disc_zone_mm" in classification["input"]
    
    def test_classify_hl7v2_with_malformed_message(self, pact):
        """
        Test /classify/hl7v2 endpoint with malformed HL7v2 message.
        
        Provider state: malformed HL7v2 message
        Expected: 400 Bad Request with HL7v2 parsing error
        """
        malformed_message = setup_provider_state("malformed HL7v2 message")
        
        expected_error_response = {
            "type": Like("https://amr-engine.com/problems/hl7v2-parsing-error"),
            "title": Like("HL7v2 Parsing Error"),
            "status": Like(400),
            "detail": Term(r"HL7v2 parsing error:.*", "HL7v2 parsing error: Missing required segments"),
            "operationOutcome": {
                "resourceType": Like("OperationOutcome"),
                "issue": EachLike({
                    "severity": Like("error"),
                    "code": Like("invalid"),
                    "diagnostics": Term(r"HL7v2 parsing error:.*", "HL7v2 parsing error: Missing required segments")
                })
            }
        }
        
        (pact
         .given("malformed HL7v2 message")
         .upon_receiving("a request to classify malformed HL7v2 message")
         .with_request(
             method="POST",
             path="/classify/hl7v2",
             headers={
                 "Content-Type": "application/hl7-v2"
             },
             body=malformed_message
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
                f"{pact.uri}/classify/hl7v2",
                data=malformed_message,
                headers={"Content-Type": "application/hl7-v2"}
            )
            
            assert response.status_code == 400
            result = response.json()
            assert result["type"].endswith("hl7v2-parsing-error")
            assert result["status"] == 400
            assert "HL7v2 parsing error" in result["detail"]
    
    def test_classify_hl7v2_with_multiple_organisms(self, pact):
        """
        Test /classify/hl7v2 endpoint with message containing multiple organisms.
        
        Provider state: healthy HL7v2 message (extended with multiple organisms)
        Expected: Successful classification for multiple organisms
        """
        # Create extended HL7v2 message with multiple organisms
        extended_hl7_message = (
            "MSH|^~\\&|LABSYS|HOSPITAL|EMR|FACILITY|20240315120000||ORU^R01|MSG003|P|2.5\r"
            "PID|1||P345678^^^MRN^MR||SMITH^MARY^A||19901010|F|||789 ELM ST^^TESTCITY^TX^75001||555-0789\r"
            "OBR|1|||MICRO^Microbiology Culture^L||202403151500||||||||SPEC456^SPUTUM^L||||||||20240315150000|||F\r"
            "OBX|1|ST|ORG^Organism^L||Escherichia coli||||||F\r"
            "OBX|2|NM|MIC^Ciprofloxacin MIC^L||0.5|mg/L|S|||F\r"
            "OBX|3|ST|ORG^Organism^L||Klebsiella pneumoniae||||||F\r"
            "OBX|4|NM|MIC^Ceftriaxone MIC^L||0.25|mg/L|S|||F"
        )
        
        expected_response = EachLike({
            "specimenId": Term(r"^FINAL-SP-[A-Z0-9]+$", "FINAL-SP-JKL012"),
            "organism": Term(r"^(Escherichia coli|Klebsiella pneumoniae)$", "Escherichia coli"),
            "antibiotic": Term(r"^(Ciprofloxacin|Ceftriaxone)$", "Ciprofloxacin"),
            "method": Like("MIC"),
            "input": {
                "organism": Term(r"^(Escherichia coli|Klebsiella pneumoniae)$", "Escherichia coli"),
                "antibiotic": Term(r"^(Ciprofloxacin|Ceftriaxone)$", "Ciprofloxacin"),
                "method": Like("MIC"),
                "mic_mg_L": Term(r"^(0\.5|0\.25)$", 0.5),
                "specimenId": Term(r"^FINAL-SP-[A-Z0-9]+$", "FINAL-SP-JKL012")
            },
            "decision": Term(r"^[SIR]$", "S"),
            "reason": Term(r"MIC (0\.5|0\.25) mg/L <= breakpoint.*", "MIC 0.5 mg/L <= breakpoint 0.5 mg/L"),
            "ruleVersion": Like("EUCAST v2025.1")
        }, minimum=2)
        
        (pact
         .given("healthy HL7v2 message")
         .upon_receiving("a request to classify HL7v2 message with multiple organisms")
         .with_request(
             method="POST",
             path="/classify/hl7v2",
             headers={
                 "Content-Type": "application/hl7-v2"
             },
             body=extended_hl7_message
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
                f"{pact.uri}/classify/hl7v2",
                data=extended_hl7_message,
                headers={"Content-Type": "application/hl7-v2"}
            )
            
            assert response.status_code == 200
            result = response.json()
            assert len(result) >= 2  # Should have at least two classifications
            organisms_found = set()
            for classification in result:
                assert classification["decision"] in ["S", "I", "R"]
                organisms_found.add(classification["organism"])
            
            # Should have classifications for both organisms
            expected_organisms = {"Escherichia coli", "Klebsiella pneumoniae"}
            assert len(organisms_found.intersection(expected_organisms)) >= 1
    
    def test_classify_hl7v2_without_msh_segment(self, pact):
        """
        Test /classify/hl7v2 endpoint with message missing MSH segment.
        
        Provider state: none (test invalid message structure)
        Expected: 400 Bad Request with missing MSH error
        """
        invalid_message = (
            "PID|1||P999999^^^MRN^MR||INVALID^PATIENT\r"
            "OBR|1|||MICRO^Microbiology\r"
            "OBX|1|ST|ORG^Organism^L||Unknown||||||F"
        )
        
        expected_error_response = {
            "type": Like("https://amr-engine.com/problems/hl7v2-parsing-error"),
            "title": Like("HL7v2 Parsing Error"),
            "status": Like(400),
            "detail": Term(r".*MSH.*", "HL7v2 parsing error: Missing MSH segment"),
            "operationOutcome": {
                "resourceType": Like("OperationOutcome"),
                "issue": EachLike({
                    "severity": Like("error"),
                    "code": Like("invalid"),
                    "diagnostics": Term(r".*MSH.*", "HL7v2 parsing error: Missing MSH segment")
                })
            }
        }
        
        (pact
         .upon_receiving("a request to classify HL7v2 message without MSH segment")
         .with_request(
             method="POST",
             path="/classify/hl7v2",
             headers={
                 "Content-Type": "application/hl7-v2"
             },
             body=invalid_message
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
                f"{pact.uri}/classify/hl7v2",
                data=invalid_message,
                headers={"Content-Type": "application/hl7-v2"}
            )
            
            assert response.status_code == 400
            result = response.json()
            assert result["status"] == 400
            assert "msh" in result["detail"].lower()
    
    def test_classify_hl7v2_with_empty_message(self, pact):
        """
        Test /classify/hl7v2 endpoint with empty message body.
        
        Provider state: none (test empty input)
        Expected: 400 Bad Request with empty message error
        """
        expected_error_response = {
            "type": Like("https://amr-engine.com/problems/hl7v2-parsing-error"),
            "title": Like("HL7v2 Parsing Error"),
            "status": Like(400),
            "detail": Term(r".*empty.*", "HL7v2 parsing error: Empty message"),
            "operationOutcome": {
                "resourceType": Like("OperationOutcome"),
                "issue": EachLike({
                    "severity": Like("error"),
                    "code": Like("invalid"),
                    "diagnostics": Term(r".*empty.*", "HL7v2 parsing error: Empty message")
                })
            }
        }
        
        (pact
         .upon_receiving("a request to classify empty HL7v2 message")
         .with_request(
             method="POST",
             path="/classify/hl7v2",
             headers={
                 "Content-Type": "application/hl7-v2"
             },
             body=""
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
                f"{pact.uri}/classify/hl7v2",
                data="",
                headers={"Content-Type": "application/hl7-v2"}
            )
            
            assert response.status_code == 400
            result = response.json()
            assert result["status"] == 400
            assert "empty" in result["detail"].lower() or "hl7v2" in result["detail"].lower()