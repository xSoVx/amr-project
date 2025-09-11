"""
Pact contract testing suite for AMR classification microservice.

This package contains consumer contract tests for the AMR classification
service, ensuring API compatibility between consumers and providers.

Modules:
    provider_states: Provider state management for test scenarios
    test_classify_contract: Contract tests for /classify endpoint
    test_classify_fhir_contract: Contract tests for /classify/fhir endpoint
    test_classify_hl7v2_contract: Contract tests for /classify/hl7v2 endpoint
    pact_config: Pact broker configuration and CI/CD integration
    conftest: Pytest configuration and fixtures
"""

__version__ = "1.0.0"
__author__ = "AMR Team"