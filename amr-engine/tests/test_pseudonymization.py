"""
Tests for patient identifier pseudonymization functionality.
"""

import json
import os
import tempfile
from pathlib import Path
import pytest
from unittest.mock import patch

from amr_engine.security.pseudonymization import PseudonymizationService, PseudonymizationConfig


@pytest.fixture
def temp_storage():
    """Create temporary storage directory for tests."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def pseudonymization_service(temp_storage):
    """Create pseudonymization service for tests."""
    config = PseudonymizationConfig(
        salt_key="test_salt_key_for_testing_only",
        encryption_key=None,  # Disable encryption for testing
        storage_path=temp_storage,
        dummy_id_prefix="TST",
        dummy_id_length=12
    )
    return PseudonymizationService(config)


class TestPseudonymizationService:
    """Test cases for PseudonymizationService."""
    
    def test_pseudonymize_patient_id(self, pseudonymization_service):
        """Test basic patient ID pseudonymization."""
        original_id = "PATIENT-12345"
        pseudonymized_id = pseudonymization_service.pseudonymize_identifier(original_id, "Patient")
        
        # Check pseudonym format
        assert pseudonymized_id.startswith("TST-PT-")
        assert len(pseudonymized_id.split("-")) == 3
        assert pseudonymized_id != original_id
    
    def test_consistent_pseudonymization(self, pseudonymization_service):
        """Test that pseudonymization is consistent across calls."""
        original_id = "PATIENT-12345"
        
        pseudonym1 = pseudonymization_service.pseudonymize_identifier(original_id, "Patient")
        pseudonym2 = pseudonymization_service.pseudonymize_identifier(original_id, "Patient")
        
        assert pseudonym1 == pseudonym2
    
    def test_different_ids_different_pseudonyms(self, pseudonymization_service):
        """Test that different IDs produce different pseudonyms."""
        id1 = "PATIENT-12345"
        id2 = "PATIENT-67890"
        
        pseudonym1 = pseudonymization_service.pseudonymize_identifier(id1, "Patient")
        pseudonym2 = pseudonymization_service.pseudonymize_identifier(id2, "Patient")
        
        assert pseudonym1 != pseudonym2
    
    def test_identifier_types(self, pseudonymization_service):
        """Test different identifier types produce different prefixes."""
        original_id = "12345"
        
        patient_id = pseudonymization_service.pseudonymize_identifier(original_id, "Patient")
        mrn_id = pseudonymization_service.pseudonymize_identifier(original_id, "MRN")
        specimen_id = pseudonymization_service.pseudonymize_identifier(original_id, "specimen_id")
        
        assert patient_id.startswith("TST-PT-")
        assert mrn_id.startswith("TST-MR-")
        assert specimen_id.startswith("TST-SP-")
        
        # Same original ID but different types should produce different pseudonyms
        assert patient_id != mrn_id != specimen_id
    
    def test_depseudonymization(self, pseudonymization_service):
        """Test reverse pseudonymization."""
        original_id = "PATIENT-12345"
        pseudonymized_id = pseudonymization_service.pseudonymize_identifier(original_id, "Patient")
        
        # Test depseudonymization
        recovered_id = pseudonymization_service.depseudonymize_identifier(pseudonymized_id)
        assert recovered_id == original_id
    
    def test_fhir_bundle_pseudonymization(self, pseudonymization_service):
        """Test FHIR bundle pseudonymization."""
        fhir_bundle = {
            "resourceType": "Bundle",
            "id": "test-bundle",
            "entry": [
                {
                    "resource": {
                        "resourceType": "Patient",
                        "id": "patient-123",
                        "identifier": [
                            {
                                "system": "http://hospital.example.org/mrn",
                                "value": "MRN-789"
                            }
                        ]
                    }
                },
                {
                    "resource": {
                        "resourceType": "Observation",
                        "id": "obs-456",
                        "subject": {
                            "reference": "Patient/patient-123"
                        },
                        "specimen": {
                            "reference": "Specimen/spec-789"
                        }
                    }
                }
            ]
        }
        
        pseudonymized_bundle = pseudonymization_service.pseudonymize_fhir_bundle(fhir_bundle)
        
        # Check patient ID pseudonymization
        patient_resource = pseudonymized_bundle["entry"][0]["resource"]
        assert patient_resource["id"].startswith("TST-PT-")
        assert patient_resource["id"] != "patient-123"
        
        # Check MRN pseudonymization
        assert patient_resource["identifier"][0]["value"].startswith("TST-MR-")
        assert patient_resource["identifier"][0]["value"] != "MRN-789"
        
        # Check subject reference pseudonymization
        observation = pseudonymized_bundle["entry"][1]["resource"]
        assert observation["subject"]["reference"].startswith("Patient/TST-PT-")
        
        # Check specimen reference pseudonymization
        assert observation["specimen"]["reference"].startswith("Specimen/TST-SP-")
    
    def test_hl7v2_message_pseudonymization(self, pseudonymization_service):
        """Test HL7v2 message pseudonymization."""
        hl7_message = """MSH|^~\\&|LAB|FACILITY|EMR|HOSPITAL|20240101120000||ORU^R01|12345|P|2.5
PID|1||PATIENT-123^^^MRN^MR||DOE^JOHN||19800101|M|||123 MAIN ST^ANYTOWN^ST^12345||555-1234||||||ACCT-789|123-45-6789|||||||||||
OBR|1|||MICRO^Microbiology||||||||||SPEC-456|||||||||F
OBX|1|ST|ORG^Organism||Escherichia coli||||||F
OBX|2|NM|MIC^Amoxicillin MIC||4.0|mg/L|||||F"""
        
        pseudonymized_message = pseudonymization_service.pseudonymize_hl7v2_message(hl7_message)
        
        # Check that original patient ID is not present
        assert "PATIENT-123" not in pseudonymized_message
        assert "ACCT-789" not in pseudonymized_message
        assert "SPEC-456" not in pseudonymized_message
        
        # Check that pseudonyms are present
        assert "TST-" in pseudonymized_message
    
    def test_json_data_pseudonymization(self, pseudonymization_service):
        """Test generic JSON data pseudonymization."""
        json_data = {
            "patient_id": "PATIENT-123",
            "specimen_id": "SPEC-456",
            "mrn": "MRN-789",
            "organism": "E. coli",
            "antibiotic": "Amoxicillin",
            "nested_data": {
                "patient_identifier": "PATIENT-123",
                "other_field": "not_an_id"
            }
        }
        
        pseudonymized_data = pseudonymization_service.pseudonymize_json_data(json_data)
        
        # Check pseudonymization of patient identifiers
        assert pseudonymized_data["patient_id"].startswith("TST-PT-")
        assert pseudonymized_data["patient_id"] != "PATIENT-123"
        
        assert pseudonymized_data["specimen_id"].startswith("TST-SP-")
        assert pseudonymized_data["specimen_id"] != "SPEC-456"
        
        assert pseudonymized_data["mrn"].startswith("TST-MR-")
        assert pseudonymized_data["mrn"] != "MRN-789"
        
        # Check nested pseudonymization
        assert pseudonymized_data["nested_data"]["patient_identifier"].startswith("TST-PT-")
        
        # Check non-identifier fields are unchanged
        assert pseudonymized_data["organism"] == "E. coli"
        assert pseudonymized_data["antibiotic"] == "Amoxicillin"
        assert pseudonymized_data["nested_data"]["other_field"] == "not_an_id"
    
    def test_mapping_persistence(self, temp_storage):
        """Test that mappings are persisted and loaded correctly."""
        config = PseudonymizationConfig(
            salt_key="test_salt_key_for_testing_only",
            encryption_key=None,
            storage_path=temp_storage
        )
        
        # Create first service instance and pseudonymize an ID
        service1 = PseudonymizationService(config)
        original_id = "PATIENT-12345"
        pseudonym1 = service1.pseudonymize_identifier(original_id, "Patient")
        
        # Create second service instance (simulating restart)
        service2 = PseudonymizationService(config)
        pseudonym2 = service2.pseudonymize_identifier(original_id, "Patient")
        
        # Should get same pseudonym due to persistence
        assert pseudonym1 == pseudonym2
        
        # Should be able to depseudonymize with new instance
        recovered_id = service2.depseudonymize_identifier(pseudonym1)
        assert recovered_id == original_id
    
    def test_statistics(self, pseudonymization_service):
        """Test pseudonymization statistics."""
        # Add some mappings
        pseudonymization_service.pseudonymize_identifier("PATIENT-1", "Patient")
        pseudonymization_service.pseudonymize_identifier("MRN-1", "MRN")
        pseudonymization_service.pseudonymize_identifier("SPEC-1", "specimen_id")
        
        stats = pseudonymization_service.get_pseudonymization_stats()
        
        assert stats["total_mappings"] == 3
        assert stats["type_breakdown"]["Patient"] == 1
        assert stats["type_breakdown"]["MRN"] == 1
        assert stats["type_breakdown"]["specimen_id"] == 1
        assert stats["encryption_enabled"] is False  # Disabled for tests
    
    def test_empty_and_none_identifiers(self, pseudonymization_service):
        """Test handling of empty and None identifiers."""
        # Should return original values for empty/None inputs
        assert pseudonymization_service.pseudonymize_identifier("", "Patient") == ""
        assert pseudonymization_service.pseudonymize_identifier("   ", "Patient") == "   "
        assert pseudonymization_service.pseudonymize_identifier(None, "Patient") is None


class TestPseudonymizationConfig:
    """Test cases for PseudonymizationConfig."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = PseudonymizationConfig()
        
        assert config.dummy_id_prefix == "PSY"
        assert config.dummy_id_length == 12
        assert "Patient" in config.supported_id_types
        assert "MRN" in config.supported_id_types
        assert "specimen_id" in config.supported_id_types
    
    def test_custom_config(self):
        """Test custom configuration values."""
        custom_storage = Path("/tmp/test")
        config = PseudonymizationConfig(
            salt_key="custom_salt",
            dummy_id_prefix="CUSTOM",
            dummy_id_length=8,
            storage_path=custom_storage
        )
        
        assert config.salt_key == "custom_salt"
        assert config.dummy_id_prefix == "CUSTOM"
        assert config.dummy_id_length == 8
        assert config.storage_path == custom_storage


if __name__ == "__main__":
    pytest.main([__file__])