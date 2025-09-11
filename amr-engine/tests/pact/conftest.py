"""
Pytest configuration for Pact contract tests.

This module provides pytest fixtures and configuration for running
Pact consumer contract tests against the AMR classification service.
"""

import pytest
import os
import tempfile
from pathlib import Path
from typing import Generator

from pact import Consumer, Provider


@pytest.fixture(scope="session")
def pact_dir() -> Path:
    """
    Provide the directory for storing Pact contract files.
    
    Returns:
        Path: Directory path for Pact contract files
    """
    pact_dir = Path("tests/pacts")
    pact_dir.mkdir(exist_ok=True)
    return pact_dir


@pytest.fixture(scope="session")
def mock_service_port() -> int:
    """
    Provide the port for the Pact mock service.
    
    Returns:
        int: Port number for mock service
    """
    return int(os.getenv("PACT_MOCK_SERVICE_PORT", "8080"))


@pytest.fixture(scope="session")
def provider_service_url() -> str:
    """
    Provide the URL for the provider service.
    
    Returns:
        str: Provider service base URL
    """
    host = os.getenv("PROVIDER_SERVICE_HOST", "localhost")
    port = os.getenv("PROVIDER_SERVICE_PORT", "8080")
    return f"http://{host}:{port}"


@pytest.fixture
def amr_consumer_pact(pact_dir: Path, mock_service_port: int) -> Generator:
    """
    Create Pact consumer for AMR classification service testing.
    
    Args:
        pact_dir: Directory for storing Pact files
        mock_service_port: Port for mock service
        
    Yields:
        Pact: Consumer-provider Pact instance
    """
    pact = Consumer("amr-consumer").has_pact_with(
        Provider("amr-classification-service"),
        host_name="localhost",
        port=mock_service_port,
        pact_dir=str(pact_dir)
    )
    pact.start()
    yield pact
    pact.stop()


@pytest.fixture
def amr_fhir_consumer_pact(pact_dir: Path, mock_service_port: int) -> Generator:
    """
    Create Pact consumer for FHIR-specific testing.
    
    Args:
        pact_dir: Directory for storing Pact files
        mock_service_port: Port for mock service
        
    Yields:
        Pact: Consumer-provider Pact instance for FHIR testing
    """
    pact = Consumer("amr-fhir-consumer").has_pact_with(
        Provider("amr-classification-service"),
        host_name="localhost",
        port=mock_service_port + 1,  # Use different port to avoid conflicts
        pact_dir=str(pact_dir)
    )
    pact.start()
    yield pact
    pact.stop()


@pytest.fixture
def amr_hl7v2_consumer_pact(pact_dir: Path, mock_service_port: int) -> Generator:
    """
    Create Pact consumer for HL7v2-specific testing.
    
    Args:
        pact_dir: Directory for storing Pact files
        mock_service_port: Port for mock service
        
    Yields:
        Pact: Consumer-provider Pact instance for HL7v2 testing
    """
    pact = Consumer("amr-hl7v2-consumer").has_pact_with(
        Provider("amr-classification-service"),
        host_name="localhost",
        port=mock_service_port + 2,  # Use different port to avoid conflicts
        pact_dir=str(pact_dir)
    )
    pact.start()
    yield pact
    pact.stop()


@pytest.fixture(autouse=True)
def setup_test_environment():
    """
    Set up test environment variables and configuration.
    
    This fixture automatically runs for all tests and ensures
    consistent test environment setup.
    """
    # Set test-specific environment variables
    os.environ.setdefault("AMR_RULES_PATH", "amr_engine/rules/eucast_v_2025_1.yaml")
    os.environ.setdefault("LOG_LEVEL", "INFO")
    os.environ.setdefault("REDIS_ENABLED", "false")
    
    # Ensure Pact directory exists
    pact_dir = Path("tests/pacts")
    pact_dir.mkdir(exist_ok=True)
    
    yield
    
    # Cleanup if needed
    pass


def pytest_configure(config):
    """
    Configure pytest for Pact testing.
    
    Args:
        config: Pytest configuration object
    """
    # Add custom markers
    config.addinivalue_line(
        "markers", "pact: mark test as a Pact contract test"
    )
    config.addinivalue_line(
        "markers", "consumer: mark test as a consumer contract test"
    )
    config.addinivalue_line(
        "markers", "provider: mark test as a provider verification test"
    )


def pytest_collection_modifyitems(config, items):
    """
    Modify collected test items to add markers automatically.
    
    Args:
        config: Pytest configuration object
        items: List of collected test items
    """
    for item in items:
        # Add pact marker to all tests in pact directory
        if "test_pact" in str(item.fspath) or "pact" in str(item.fspath):
            item.add_marker(pytest.mark.pact)
        
        # Add specific markers based on test names
        if "consumer" in item.name.lower():
            item.add_marker(pytest.mark.consumer)
        if "provider" in item.name.lower():
            item.add_marker(pytest.mark.provider)