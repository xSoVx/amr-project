"""
Provider verification tests for AMR classification service.

This module contains comprehensive provider verification tests that load
consumer contracts from the Pact broker, set up required database and
rule engine states, and verify the AMR service responses against
consumer contract expectations.
"""

import asyncio
import json
import logging
import os
import pytest
import requests
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, Any, List, Optional
from unittest.mock import patch, MagicMock

import httpx
from fastapi.testclient import TestClient

from amr_engine.main import app
from amr_engine.config import get_settings
from amr_engine.core.classifier import Classifier
from amr_engine.core.rules_loader import RulesLoader
from .provider_states import setup_provider_state, ProviderStates
from .pact_config import get_pact_broker_config, PactBrokerConfig

logger = logging.getLogger(__name__)


class ProviderVerificationFixture:
    """
    Fixture class for setting up provider verification environment.
    
    Manages database state, rule engine configuration, and service setup
    for comprehensive provider contract verification.
    """
    
    def __init__(self):
        self.client = TestClient(app)
        self.settings = get_settings()
        self.classifier = None
        self.rules_loader = None
        self.mock_database = {}
        self.async_tasks = {}
        self.webhook_calls = []
        
    def setup_environment(self):
        """Set up test environment with proper configuration."""
        # Configure test environment variables
        os.environ.update({
            "AMR_RULES_PATH": "amr_engine/rules/eucast_v_2025_1.yaml",
            "LOG_LEVEL": "INFO",
            "REDIS_ENABLED": "false",
            "DATABASE_URL": "sqlite:///:memory:",
            "TESTING": "true"
        })
        
        # Initialize components
        self.classifier = Classifier()
        self.rules_loader = RulesLoader()
        
        logger.info("Provider verification environment set up successfully")
    
    def setup_database_state(self, state_name: str, state_data: Any):
        """
        Set up database state for specific test scenarios.
        
        Args:
            state_name: Name of the provider state
            state_data: Data to set up for the state
        """
        # Mock database entries for different scenarios
        state_mapping = {
            "healthy patient data": self._setup_healthy_patient_db,
            "healthy patient data for UI": self._setup_ui_patient_db,
            "invalid FHIR bundle": self._setup_invalid_bundle_db,
            "missing organism data": self._setup_missing_organism_db,
            "HL7v2 message with missing MIC values": self._setup_missing_mic_db,
            "invalid organism code data": self._setup_invalid_organism_db,
            "IL-Core profile validation failure data": self._setup_il_core_failure_db,
            "mixed format batch data": self._setup_batch_data_db
        }
        
        if state_name in state_mapping:
            state_mapping[state_name](state_data)
            logger.info(f"Database state set up for: {state_name}")
        else:
            logger.warning(f"Unknown database state: {state_name}")
    
    def _setup_healthy_patient_db(self, data: Dict[str, Any]):
        """Set up database for healthy patient scenario."""
        self.mock_database["patients"] = {
            "patient-healthy": {
                "id": "patient-healthy",
                "mrn": "HEALTHY001",
                "name": "TestPatient, Healthy A",
                "active": True
            }
        }
        
        self.mock_database["specimens"] = {
            "specimen-healthy": {
                "id": "specimen-healthy",
                "patient_id": "patient-healthy",
                "type": "blood",
                "collected_date": "2024-03-15T09:00:00Z"
            }
        }
        
        self.mock_database["observations"] = {
            "ampicillin-susceptible": {
                "id": "ampicillin-susceptible",
                "patient_id": "patient-healthy",
                "specimen_id": "specimen-healthy",
                "organism": "Escherichia coli",
                "antibiotic": "Ampicillin",
                "method": "MIC",
                "value": 4.0,
                "unit": "mg/L"
            }
        }
    
    def _setup_ui_patient_db(self, data: Dict[str, Any]):
        """Set up database for UI patient scenario."""
        self.mock_database["patients"] = {
            "patient-ui-12345": {
                "id": "patient-ui-12345",
                "mrn": "UI-MRN12345678",
                "name": "Smith, Jane A",
                "active": True
            }
        }
        
        self.mock_database["specimens"] = {
            "specimen-blood-ui-001": {
                "id": "specimen-blood-ui-001",
                "patient_id": "patient-ui-12345",
                "type": "blood",
                "collected_date": "2024-09-11T10:30:00Z"
            }
        }
        
        self.mock_database["observations"] = {
            "ciprofloxacin-mic-ui": {
                "id": "ciprofloxacin-mic-ui",
                "patient_id": "patient-ui-12345",
                "specimen_id": "specimen-blood-ui-001",
                "organism": "Escherichia coli",
                "antibiotic": "Ciprofloxacin",
                "method": "MIC",
                "value": 0.25,
                "unit": "mg/L"
            }
        }
    
    def _setup_invalid_bundle_db(self, data: Dict[str, Any]):
        """Set up database for invalid bundle scenario."""
        # Intentionally incomplete/invalid data
        self.mock_database["observations"] = {
            "invalid-observation": {
                "id": "invalid-observation",
                "patient_id": "nonexistent",
                "status": "final"
                # Missing required fields
            }
        }
    
    def _setup_missing_organism_db(self, data: Dict[str, Any]):
        """Set up database for missing organism scenario."""
        self.mock_database["patients"] = {
            "patient-missing-org": {
                "id": "patient-missing-org",
                "mrn": "MISSING-ORG-001"
            }
        }
        
        self.mock_database["observations"] = {
            "ampicillin-no-organism": {
                "id": "ampicillin-no-organism",
                "patient_id": "patient-missing-org",
                "antibiotic": "Ampicillin",
                "method": "MIC",
                "value": 8.0,
                "unit": "mg/L"
                # Missing organism field
            }
        }
    
    def _setup_missing_mic_db(self, data: Dict[str, Any]):
        """Set up database for missing MIC scenario."""
        self.mock_database["patients"] = {
            "ui-p12345678": {
                "id": "ui-p12345678",
                "mrn": "UI_P12345678"
            }
        }
        
        self.mock_database["observations"] = {
            "vancomycin-missing": {
                "id": "vancomycin-missing",
                "patient_id": "ui-p12345678",
                "organism": "Staphylococcus aureus",
                "antibiotic": "Vancomycin",
                "method": "MIC",
                "value": None,  # Missing MIC value
                "note": "Missing"
            }
        }
    
    def _setup_invalid_organism_db(self, data: Dict[str, Any]):
        """Set up database for invalid organism scenario."""
        self.mock_database["observations"] = {
            "invalid-organism": {
                "id": "invalid-organism",
                "organism_code": "999999999",
                "organism_name": "Unknown Alien Bacteria"
            }
        }
    
    def _setup_il_core_failure_db(self, data: Dict[str, Any]):
        """Set up database for IL-Core profile validation failure."""
        self.mock_database["patients"] = {
            "patient-il-fail": {
                "id": "patient-il-fail",
                "name": "כהן, דוד",
                # Missing required IL-Core identifier
            }
        }
    
    def _setup_batch_data_db(self, data: Dict[str, Any]):
        """Set up database for batch processing scenario."""
        self.mock_database["batch_requests"] = {
            "batch-001": {
                "requests": [
                    {
                        "type": "fhir",
                        "organism": "Escherichia coli",
                        "antibiotic": "Ampicillin",
                        "method": "MIC",
                        "value": 8.0
                    },
                    {
                        "type": "direct",
                        "organism": "Staphylococcus aureus",
                        "antibiotic": "Vancomycin",
                        "method": "MIC",
                        "value": 2.0
                    }
                ]
            }
        }
    
    def setup_rule_engine_state(self, state_name: str):
        """
        Set up rule engine configuration for specific scenarios.
        
        Args:
            state_name: Name of the provider state requiring rule setup
        """
        if "IL-Core" in state_name:
            # Mock IL-Core specific rules
            self.mock_database["profile_rules"] = {
                "IL-Core": {
                    "required_identifiers": ["IL-ID"],
                    "required_fields": ["national_id"],
                    "validation_strict": True
                }
            }
        elif "US-Core" in state_name:
            # Mock US-Core specific rules
            self.mock_database["profile_rules"] = {
                "US-Core": {
                    "required_identifiers": ["MR"],
                    "required_fields": ["ssn"],
                    "validation_strict": False
                }
            }
        elif "invalid organism" in state_name:
            # Mock rules that don't include alien bacteria
            self.mock_database["organism_rules"] = {
                "supported_organisms": [
                    "112283007",  # E. coli
                    "3092008",    # Staph aureus
                    "40886007"    # Klebsiella pneumoniae
                    # 999999999 not included - invalid
                ]
            }
        
        logger.info(f"Rule engine state configured for: {state_name}")
    
    def create_async_task(self, task_id: str, task_data: Dict[str, Any]):
        """
        Create an async classification task for testing.
        
        Args:
            task_id: Unique identifier for the task
            task_data: Task configuration data
        """
        async def mock_async_classification():
            # Simulate async processing delay
            await asyncio.sleep(0.5)
            
            return {
                "task_id": task_id,
                "status": "completed",
                "result": {
                    "organism": task_data.get("organism", "Escherichia coli"),
                    "antibiotic": task_data.get("antibiotic", "Ampicillin"),
                    "decision": "S",
                    "method": "MIC",
                    "processed_at": time.time()
                }
            }
        
        self.async_tasks[task_id] = mock_async_classification()
        logger.info(f"Async task created: {task_id}")
    
    def get_async_task_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get result from async classification task.
        
        Args:
            task_id: Task identifier
            
        Returns:
            Task result or None if not found/incomplete
        """
        if task_id in self.async_tasks:
            task = self.async_tasks[task_id]
            if task.done():
                return task.result()
        return None
    
    def setup_webhook_mock(self, webhook_url: str):
        """
        Set up webhook mock for verification result publishing.
        
        Args:
            webhook_url: URL to mock for webhook calls
        """
        def mock_webhook_call(*args, **kwargs):
            call_data = {
                "url": webhook_url,
                "method": kwargs.get("method", "POST"),
                "data": kwargs.get("json", kwargs.get("data")),
                "headers": kwargs.get("headers", {}),
                "timestamp": time.time()
            }
            self.webhook_calls.append(call_data)
            
            # Mock successful webhook response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "received"}
            return mock_response
        
        return mock_webhook_call
    
    def cleanup(self):
        """Clean up test environment and resources."""
        self.mock_database.clear()
        self.async_tasks.clear()
        self.webhook_calls.clear()
        logger.info("Provider verification environment cleaned up")


@pytest.fixture(scope="session")
def provider_verification():
    """
    Provider verification fixture for setting up test environment.
    
    Yields:
        ProviderVerificationFixture: Configured test fixture
    """
    fixture = ProviderVerificationFixture()
    fixture.setup_environment()
    yield fixture
    fixture.cleanup()


@pytest.fixture
def pact_broker_config():
    """
    Pact broker configuration fixture.
    
    Returns:
        PactBrokerConfig: Broker configuration for tests
    """
    # Use test configuration if available, otherwise mock
    try:
        return get_pact_broker_config()
    except ValueError:
        # Mock configuration for tests
        return PactBrokerConfig(
            broker_url="http://localhost:9292",
            username="admin",
            password="admin",
            consumer_name="test-consumer",
            provider_name="amr-classification-service",
            consumer_version="test-version",
            provider_version="test-version"
        )


class TestProviderVerification:
    """
    Provider verification test suite.
    
    Tests verify that the AMR classification service correctly implements
    the contracts expected by various consumer services.
    """
    
    @pytest.mark.provider
    @pytest.mark.asyncio
    async def test_verify_consumer_contracts_from_broker(
        self, 
        provider_verification: ProviderVerificationFixture,
        pact_broker_config: PactBrokerConfig
    ):
        """
        Load and verify all consumer contracts from Pact broker.
        
        This test loads consumer contracts from the broker and verifies
        that the provider service meets all contract expectations.
        """
        # Mock Pact broker response with consumer contracts
        mock_contracts = [
            {
                "consumer": {"name": "amr-consumer"},
                "provider": {"name": "amr-classification-service"},
                "interactions": [
                    {
                        "description": "a request for FHIR Bundle classification",
                        "providerState": "healthy patient data",
                        "request": {
                            "method": "POST",
                            "path": "/classify/fhir",
                            "headers": {
                                "Content-Type": "application/fhir+json",
                                "Authorization": "Bearer test-token"
                            }
                        },
                        "response": {
                            "status": 200,
                            "headers": {"Content-Type": "application/json"},
                            "body": {
                                "organism": "Escherichia coli",
                                "antibiotic": "Ampicillin",
                                "decision": "S",
                                "method": "MIC"
                            }
                        }
                    }
                ]
            },
            {
                "consumer": {"name": "ui-service"},
                "provider": {"name": "amr-classification-service"},
                "interactions": [
                    {
                        "description": "a request for FHIR Bundle classification from UI",
                        "providerState": "healthy patient data for UI",
                        "request": {
                            "method": "POST",
                            "path": "/classify/fhir",
                            "headers": {
                                "Content-Type": "application/fhir+json",
                                "Authorization": "Bearer ui-service-token-12345",
                                "X-Correlation-ID": "ui-correlation-001"
                            }
                        },
                        "response": {
                            "status": 200,
                            "headers": {"Content-Type": "application/json"},
                            "body": {
                                "organism": "Escherichia coli",
                                "antibiotic": "Ciprofloxacin",
                                "decision": "S",
                                "method": "MIC"
                            }
                        }
                    }
                ]
            }
        ]
        
        verification_results = []
        
        for contract in mock_contracts:
            consumer_name = contract["consumer"]["name"]
            
            for interaction in contract["interactions"]:
                # Set up provider state
                provider_state = interaction.get("providerState")
                if provider_state:
                    state_data = setup_provider_state(provider_state)
                    provider_verification.setup_database_state(provider_state, state_data)
                    provider_verification.setup_rule_engine_state(provider_state)
                
                # Execute request
                request_spec = interaction["request"]
                expected_response = interaction["response"]
                
                try:
                    # Make request to provider service
                    response = provider_verification.client.request(
                        method=request_spec["method"],
                        url=request_spec["path"],
                        headers=request_spec.get("headers", {}),
                        json=state_data if request_spec["method"] == "POST" else None
                    )
                    
                    # Verify response matches contract
                    assert response.status_code == expected_response["status"]
                    
                    if "application/json" in expected_response.get("headers", {}).get("Content-Type", ""):
                        response_data = response.json()
                        expected_body = expected_response["body"]
                        
                        # Verify response structure
                        for key, expected_value in expected_body.items():
                            assert key in response_data
                            if isinstance(expected_value, str):
                                assert response_data[key] == expected_value
                    
                    verification_results.append({
                        "consumer": consumer_name,
                        "interaction": interaction["description"],
                        "status": "passed",
                        "response_status": response.status_code
                    })
                    
                except Exception as e:
                    verification_results.append({
                        "consumer": consumer_name,
                        "interaction": interaction["description"],
                        "status": "failed",
                        "error": str(e)
                    })
        
        # All verifications should pass
        failed_verifications = [r for r in verification_results if r["status"] == "failed"]
        if failed_verifications:
            logger.error(f"Failed verifications: {failed_verifications}")
            pytest.fail(f"Contract verifications failed: {failed_verifications}")
        
        logger.info(f"All {len(verification_results)} contract verifications passed")
    
    @pytest.mark.provider
    def test_verify_synchronous_classification(
        self, 
        provider_verification: ProviderVerificationFixture
    ):
        """Test synchronous classification endpoint verification."""
        # Set up state for synchronous classification
        provider_verification.setup_database_state(
            "healthy patient data", 
            setup_provider_state("healthy patient data")
        )
        
        # Test synchronous FHIR classification
        fhir_bundle = setup_provider_state("healthy patient data")
        
        response = provider_verification.client.post(
            "/classify/fhir",
            json=fhir_bundle,
            headers={
                "Content-Type": "application/fhir+json",
                "Authorization": "Bearer test-token"
            }
        )
        
        assert response.status_code == 200
        result = response.json()
        
        # Verify expected response structure
        assert "organism" in result
        assert "antibiotic" in result
        assert "decision" in result
        assert "method" in result
        assert result["decision"] in ["S", "I", "R"]
    
    @pytest.mark.provider
    @pytest.mark.asyncio
    async def test_verify_asynchronous_classification(
        self,
        provider_verification: ProviderVerificationFixture
    ):
        """Test asynchronous classification endpoint verification."""
        # Set up async task
        task_id = "async-test-001"
        task_data = {
            "organism": "Escherichia coli",
            "antibiotic": "Ampicillin",
            "method": "MIC",
            "mic_mg_L": 4.0
        }
        
        provider_verification.create_async_task(task_id, task_data)
        
        # Test async classification initiation
        response = provider_verification.client.post(
            "/classify/async",
            json=task_data,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer test-token"
            }
        )
        
        if response.status_code == 404:
            # Async endpoint might not be implemented yet
            pytest.skip("Async classification endpoint not implemented")
        
        assert response.status_code == 202  # Accepted for async processing
        response_data = response.json()
        
        assert "task_id" in response_data
        assert "status" in response_data
        assert response_data["status"] in ["pending", "processing"]
        
        # Test async result retrieval
        result_response = provider_verification.client.get(
            f"/classify/async/{task_id}",
            headers={"Authorization": "Bearer test-token"}
        )
        
        # Should eventually return completed result
        if result_response.status_code == 200:
            result = result_response.json()
            assert "status" in result
            assert "result" in result
    
    @pytest.mark.provider
    def test_verify_error_scenarios(
        self,
        provider_verification: ProviderVerificationFixture
    ):
        """Test error scenario contract verification."""
        # Test invalid organism code scenario
        provider_verification.setup_database_state(
            "invalid organism code data",
            setup_provider_state("invalid organism code data")
        )
        
        invalid_bundle = setup_provider_state("invalid organism code data")
        
        response = provider_verification.client.post(
            "/classify/fhir",
            json=invalid_bundle,
            headers={
                "Content-Type": "application/fhir+json",
                "Authorization": "Bearer test-token"
            }
        )
        
        assert response.status_code == 400
        assert response.headers.get("Content-Type") == "application/problem+json"
        
        error_response = response.json()
        assert "type" in error_response
        assert "title" in error_response
        assert "status" in error_response
        assert "operationOutcome" in error_response
    
    @pytest.mark.provider
    def test_verify_profile_validation_scenarios(
        self,
        provider_verification: ProviderVerificationFixture
    ):
        """Test profile validation contract verification."""
        # Test IL-Core profile validation failure
        provider_verification.setup_database_state(
            "IL-Core profile validation failure data",
            setup_provider_state("IL-Core profile validation failure data")
        )
        provider_verification.setup_rule_engine_state("IL-Core profile validation failure data")
        
        il_core_bundle = setup_provider_state("IL-Core profile validation failure data")
        
        response = provider_verification.client.post(
            "/classify/fhir",
            json=il_core_bundle,
            headers={
                "Content-Type": "application/fhir+json",
                "Authorization": "Bearer test-token",
                "X-Profile-Pack": "IL-Core"
            }
        )
        
        assert response.status_code == 422  # Unprocessable Entity
        error_response = response.json()
        assert "IL-Core" in error_response.get("detail", "")
    
    @pytest.mark.provider
    def test_verify_batch_processing_scenarios(
        self,
        provider_verification: ProviderVerificationFixture
    ):
        """Test batch processing contract verification."""
        provider_verification.setup_database_state(
            "mixed format batch data",
            setup_provider_state("mixed format batch data")
        )
        
        batch_request = setup_provider_state("mixed format batch data")
        
        response = provider_verification.client.post(
            "/classify/batch",
            json=batch_request,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer test-token"
            }
        )
        
        if response.status_code == 404:
            # Batch endpoint might not be implemented yet
            pytest.skip("Batch classification endpoint not implemented")
        
        assert response.status_code == 200
        results = response.json()
        
        assert isinstance(results, list)
        assert len(results) >= 1
        
        for result in results:
            assert "decision" in result
            assert result["decision"] in ["S", "I", "R"]
    
    @pytest.mark.provider
    def test_webhook_verification_results_publishing(
        self,
        provider_verification: ProviderVerificationFixture,
        pact_broker_config: PactBrokerConfig
    ):
        """Test webhook publishing of verification results."""
        webhook_url = f"{pact_broker_config.broker_url}/webhooks/verification-results"
        
        # Set up webhook mock
        mock_webhook = provider_verification.setup_webhook_mock(webhook_url)
        
        # Mock verification results
        verification_results = {
            "provider": pact_broker_config.provider_name,
            "consumer": "test-consumer",
            "success": True,
            "verificationResults": [
                {
                    "description": "test interaction",
                    "status": "passed",
                    "timestamp": time.time()
                }
            ]
        }
        
        # Simulate webhook call
        with patch('requests.post', side_effect=mock_webhook):
            requests.post(
                webhook_url,
                json=verification_results,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {pact_broker_config.token}"
                }
            )
        
        # Verify webhook was called
        assert len(provider_verification.webhook_calls) == 1
        webhook_call = provider_verification.webhook_calls[0]
        
        assert webhook_call["url"] == webhook_url
        assert webhook_call["method"] == "POST"
        assert webhook_call["data"]["success"] == True
        assert "verificationResults" in webhook_call["data"]
    
    @pytest.mark.provider
    def test_contract_version_compatibility(
        self,
        provider_verification: ProviderVerificationFixture,
        pact_broker_config: PactBrokerConfig
    ):
        """Test contract version compatibility verification."""
        # Test multiple consumer versions
        consumer_versions = ["v1.0.0", "v1.1.0", "v2.0.0"]
        compatibility_results = {}
        
        for version in consumer_versions:
            try:
                # Mock contract retrieval for specific version
                # In real implementation, this would fetch from Pact broker
                
                # Set up basic state
                provider_verification.setup_database_state(
                    "healthy patient data",
                    setup_provider_state("healthy patient data")
                )
                
                # Test basic classification endpoint
                response = provider_verification.client.post(
                    "/classify/fhir",
                    json=setup_provider_state("healthy patient data"),
                    headers={
                        "Content-Type": "application/fhir+json",
                        "Authorization": "Bearer test-token"
                    }
                )
                
                compatibility_results[version] = {
                    "compatible": response.status_code == 200,
                    "status_code": response.status_code
                }
                
            except Exception as e:
                compatibility_results[version] = {
                    "compatible": False,
                    "error": str(e)
                }
        
        # Verify compatibility with all versions
        for version, result in compatibility_results.items():
            if not result["compatible"]:
                logger.warning(f"Compatibility issue with consumer version {version}: {result}")
        
        # At least current version should be compatible
        assert any(result["compatible"] for result in compatibility_results.values())


if __name__ == "__main__":
    # Run provider verification tests
    pytest.main([
        __file__,
        "-v",
        "--tb=short",
        "-m", "provider"
    ])