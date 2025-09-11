"""
Provider state management for Pact verification testing.

This module provides comprehensive state management for provider verification tests,
including database setup, rule engine configuration, and external service mocking.
"""

import asyncio
import json
import logging
import os
import tempfile
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, List, Optional, AsyncGenerator
from unittest.mock import patch, MagicMock

import yaml
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from amr_engine.config import get_settings
from amr_engine.core.classifier import Classifier
from amr_engine.core.rules_loader import RulesLoader

logger = logging.getLogger(__name__)


@dataclass
class DatabaseState:
    """Database state configuration for provider verification."""
    
    patients: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    specimens: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    observations: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    organizations: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    practitioners: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    classifications: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    audit_logs: List[Dict[str, Any]] = field(default_factory=list)
    
    def clear(self):
        """Clear all database state."""
        for attr in ['patients', 'specimens', 'observations', 'organizations', 'practitioners', 'classifications']:
            getattr(self, attr).clear()
        self.audit_logs.clear()


@dataclass
class RuleEngineState:
    """Rule engine state configuration for provider verification."""
    
    rules_version: str = "EUCAST v2025.1"
    organism_rules: Dict[str, Any] = field(default_factory=dict)
    antibiotic_rules: Dict[str, Any] = field(default_factory=dict)
    profile_rules: Dict[str, Any] = field(default_factory=dict)
    breakpoint_overrides: Dict[str, Any] = field(default_factory=dict)
    custom_rules: List[Dict[str, Any]] = field(default_factory=list)
    
    def clear(self):
        """Clear all rule engine state."""
        self.organism_rules.clear()
        self.antibiotic_rules.clear()
        self.profile_rules.clear()
        self.breakpoint_overrides.clear()
        self.custom_rules.clear()


class ProviderStateManager:
    """
    Comprehensive provider state manager for Pact verification tests.
    
    Manages database state, rule engine configuration, external service mocks,
    and async task simulation for thorough provider contract verification.
    """
    
    def __init__(self):
        self.db_state = DatabaseState()
        self.rule_state = RuleEngineState()
        self.settings = get_settings()
        self.temp_dir = None
        self.mock_patches = []
        self.async_tasks = {}
        self.webhook_history = []
        
        # Initialize test database
        self.db_engine = None
        self.db_session_factory = None
        self._initialize_test_database()
        
        # Initialize rule engine
        self.classifier = None
        self.rules_loader = None
        self._initialize_rule_engine()
    
    def _initialize_test_database(self):
        """Initialize in-memory test database."""
        try:
            # Use in-memory SQLite for testing
            self.db_engine = create_engine(
                "sqlite:///:memory:",
                echo=False,
                pool_pre_ping=True
            )
            self.db_session_factory = sessionmaker(bind=self.db_engine)
            
            # Create basic tables for testing
            with self.db_engine.connect() as conn:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS patients (
                        id TEXT PRIMARY KEY,
                        mrn TEXT,
                        name TEXT,
                        gender TEXT,
                        birth_date TEXT,
                        active BOOLEAN DEFAULT TRUE,
                        metadata TEXT
                    )
                """))
                
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS specimens (
                        id TEXT PRIMARY KEY,
                        patient_id TEXT,
                        type TEXT,
                        collected_date TEXT,
                        status TEXT DEFAULT 'active',
                        metadata TEXT,
                        FOREIGN KEY (patient_id) REFERENCES patients(id)
                    )
                """))
                
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS observations (
                        id TEXT PRIMARY KEY,
                        patient_id TEXT,
                        specimen_id TEXT,
                        organism TEXT,
                        antibiotic TEXT,
                        method TEXT,
                        value REAL,
                        unit TEXT,
                        status TEXT DEFAULT 'final',
                        metadata TEXT,
                        FOREIGN KEY (patient_id) REFERENCES patients(id),
                        FOREIGN KEY (specimen_id) REFERENCES specimens(id)
                    )
                """))
                
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS classifications (
                        id TEXT PRIMARY KEY,
                        observation_id TEXT,
                        organism TEXT,
                        antibiotic TEXT,
                        method TEXT,
                        decision TEXT,
                        reason TEXT,
                        rule_version TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        metadata TEXT,
                        FOREIGN KEY (observation_id) REFERENCES observations(id)
                    )
                """))
                
                conn.commit()
            
            logger.info("Test database initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize test database: {e}")
            raise
    
    def _initialize_rule_engine(self):
        """Initialize rule engine for testing."""
        try:
            self.classifier = Classifier()
            self.rules_loader = RulesLoader()
            logger.info("Rule engine initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize rule engine: {e}")
            # Continue with mock classifier for testing
            self.classifier = MagicMock()
            self.rules_loader = MagicMock()
    
    def setup_provider_state(self, state_name: str, state_params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Set up provider state for specific test scenario.
        
        Args:
            state_name: Name of the provider state to set up
            state_params: Additional parameters for state setup
            
        Returns:
            Dict containing state data for the scenario
        """
        state_params = state_params or {}
        
        # Define state setup methods
        state_methods = {
            "healthy patient data": self._setup_healthy_patient_state,
            "healthy patient data for UI": self._setup_ui_patient_state,
            "invalid FHIR bundle": self._setup_invalid_bundle_state,
            "missing organism data": self._setup_missing_organism_state,
            "HL7v2 message with missing MIC values": self._setup_missing_mic_state,
            "invalid organism code data": self._setup_invalid_organism_state,
            "IL-Core profile validation failure data": self._setup_il_core_failure_state,
            "mixed format batch data": self._setup_batch_data_state,
            "healthy HL7v2 message": self._setup_healthy_hl7v2_state,
            "malformed HL7v2 message": self._setup_malformed_hl7v2_state,
            "direct classification input": self._setup_direct_input_state,
            "invalid classification input": self._setup_invalid_input_state,
        }
        
        if state_name not in state_methods:
            logger.warning(f"Unknown provider state: {state_name}")
            return {}
        
        try:
            state_data = state_methods[state_name](state_params)
            self._persist_state_to_database(state_name, state_data)
            self._configure_rule_engine_for_state(state_name, state_params)
            
            logger.info(f"Provider state '{state_name}' set up successfully")
            return state_data
            
        except Exception as e:
            logger.error(f"Failed to set up provider state '{state_name}': {e}")
            raise
    
    def _setup_healthy_patient_state(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Set up healthy patient scenario state."""
        patient_data = {
            "id": "patient-healthy",
            "mrn": "HEALTHY001",
            "name": "TestPatient, Healthy A",
            "gender": "female",
            "birth_date": "1990-01-01",
            "active": True
        }
        
        specimen_data = {
            "id": "specimen-healthy",
            "patient_id": "patient-healthy",
            "type": "blood",
            "collected_date": "2024-03-15T09:00:00Z",
            "status": "active"
        }
        
        observation_data = {
            "id": "ampicillin-susceptible",
            "patient_id": "patient-healthy",
            "specimen_id": "specimen-healthy",
            "organism": "Escherichia coli",
            "antibiotic": "Ampicillin",
            "method": "MIC",
            "value": 4.0,
            "unit": "mg/L",
            "status": "final"
        }
        
        self.db_state.patients["patient-healthy"] = patient_data
        self.db_state.specimens["specimen-healthy"] = specimen_data
        self.db_state.observations["ampicillin-susceptible"] = observation_data
        
        return {
            "resourceType": "Bundle",
            "id": "healthy-patient-bundle",
            "type": "collection",
            "entry": [
                {"resource": self._create_fhir_patient(patient_data)},
                {"resource": self._create_fhir_specimen(specimen_data)},
                {"resource": self._create_fhir_observation(observation_data)}
            ]
        }
    
    def _setup_ui_patient_state(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Set up UI-specific patient scenario state."""
        patient_data = {
            "id": "patient-ui-12345",
            "mrn": "UI-MRN12345678",
            "name": "Smith, Jane A",
            "gender": "female",
            "birth_date": "1985-06-20",
            "active": True
        }
        
        specimen_data = {
            "id": "specimen-blood-ui-001",
            "patient_id": "patient-ui-12345",
            "type": "blood",
            "collected_date": "2024-09-11T10:30:00Z",
            "status": "active"
        }
        
        observation_data = {
            "id": "ciprofloxacin-mic-ui",
            "patient_id": "patient-ui-12345",
            "specimen_id": "specimen-blood-ui-001",
            "organism": "Escherichia coli",
            "antibiotic": "Ciprofloxacin",
            "method": "MIC",
            "value": 0.25,
            "unit": "mg/L",
            "status": "final"
        }
        
        self.db_state.patients["patient-ui-12345"] = patient_data
        self.db_state.specimens["specimen-blood-ui-001"] = specimen_data
        self.db_state.observations["ciprofloxacin-mic-ui"] = observation_data
        
        return {
            "resourceType": "Bundle",
            "id": "bundle-ecoli-ui-001",
            "type": "collection",
            "entry": [
                {"resource": self._create_fhir_patient(patient_data)},
                {"resource": self._create_fhir_specimen(specimen_data)},
                {"resource": self._create_fhir_observation(observation_data)}
            ]
        }
    
    def _setup_missing_mic_state(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Set up missing MIC scenario state."""
        observation_data = {
            "id": "vancomycin-missing-mic",
            "organism": "Staphylococcus aureus",
            "antibiotic": "Vancomycin",
            "method": "MIC",
            "value": None,  # Missing MIC value
            "unit": "mg/L",
            "note": "Missing MIC value"
        }
        
        self.db_state.observations["vancomycin-missing-mic"] = observation_data
        
        # Return HL7v2 message with missing MIC
        return (
            "MSH|^~\\&|UI_SYSTEM|UI_LAB|EMR|MAIN_HOSPITAL|20240911103000||ORU^R01|UI_MSG001|P|2.5\r"
            "PID|1||UI_P12345678^^^MRN^MR||JONES^MICHAEL^R||19750308|M|||456 ELM ST^^ANYTOWN^CA^90210||555-9876|||987654321\r"
            "OBR|1|||MICRO^Microbiology Culture^L||202409111000||||||||UI_SPEC002^BLOOD^L||||||||20240911103000|||F\r"
            "OBX|1|ST|ORG^Organism^L||Staphylococcus aureus||||||F\r"
            "OBX|2|ST|MIC^Vancomycin MIC^L||Missing|mg/L||||F\r"
        )
    
    def _setup_invalid_organism_state(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Set up invalid organism code scenario state."""
        # Configure rule engine to reject organism code 999999999
        self.rule_state.organism_rules = {
            "supported_organisms": [
                {"code": "112283007", "display": "Escherichia coli"},
                {"code": "3092008", "display": "Staphylococcus aureus"},
                {"code": "40886007", "display": "Klebsiella pneumoniae"}
                # 999999999 not included - will be rejected
            ]
        }
        
        return {
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
                        "resourceType": "Observation",
                        "id": "invalid-organism",
                        "status": "final",
                        "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category", "code": "laboratory"}]}],
                        "code": {"coding": [{"system": "http://loinc.org", "code": "634-6", "display": "Bacteria identified in Specimen by Culture"}]},
                        "subject": {"reference": "Patient/patient-ui-99999"},
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
    
    def _setup_il_core_failure_state(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Set up IL-Core profile validation failure state."""
        # Configure strict IL-Core validation rules
        self.rule_state.profile_rules["IL-Core"] = {
            "required_identifiers": ["IL-ID"],
            "required_fields": ["national_id"],
            "validation_strict": True,
            "hebrew_names_required": True
        }
        
        return {
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
                }
            ]
        }
    
    def _setup_batch_data_state(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Set up batch processing scenario state."""
        batch_observations = [
            {
                "id": "batch-obs-1",
                "organism": "Escherichia coli",
                "antibiotic": "Ampicillin",
                "method": "MIC",
                "value": 8.0,
                "unit": "mg/L"
            },
            {
                "id": "batch-obs-2",
                "organism": "Staphylococcus aureus",
                "antibiotic": "Vancomycin",
                "method": "MIC",
                "value": 2.0,
                "unit": "mg/L"
            }
        ]
        
        for obs in batch_observations:
            self.db_state.observations[obs["id"]] = obs
        
        return {
            "requests": [
                {
                    "type": "fhir",
                    "data": {
                        "resourceType": "Observation",
                        "id": "batch-obs-1",
                        "status": "final",
                        "valueQuantity": {"value": 8, "unit": "mg/L"},
                        "component": [
                            {
                                "code": {"coding": [{"system": "http://loinc.org", "code": "634-6"}]},
                                "valueCodeableConcept": {
                                    "coding": [{"system": "http://snomed.info/sct", "code": "112283007", "display": "Escherichia coli"}]
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
    
    def _setup_invalid_bundle_state(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Set up invalid FHIR bundle state."""
        return {
            "resourceType": "Bundle",
            "id": "invalid-bundle",
            "type": "collection",
            "entry": [
                {
                    "resource": {
                        "resourceType": "Observation",
                        "id": "invalid-observation",
                        "status": "final",
                        # Missing required code element
                        "subject": {"reference": "Patient/nonexistent"},
                        "valueQuantity": {
                            # Missing required value
                            "unit": "mg/L"
                        }
                    }
                }
            ]
        }
    
    def _setup_missing_organism_state(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Set up missing organism data state."""
        return {
            "resourceType": "Bundle",
            "id": "missing-organism-bundle",
            "type": "collection",
            "entry": [
                {
                    "resource": {
                        "resourceType": "Patient",
                        "id": "patient-missing-org",
                        "identifier": [{"value": "MISSING-ORG-001"}]
                    }
                },
                {
                    "resource": {
                        "resourceType": "Observation",
                        "id": "ampicillin-no-organism",
                        "status": "final",
                        "code": {"coding": [{"system": "http://loinc.org", "code": "18864-9"}]},
                        "subject": {"reference": "Patient/patient-missing-org"},
                        "valueQuantity": {"value": 8.0, "unit": "mg/L"}
                        # Missing organism information
                    }
                }
            ]
        }
    
    def _setup_healthy_hl7v2_state(self, params: Dict[str, Any]) -> str:
        """Set up healthy HL7v2 message state."""
        return (
            "MSH|^~\\&|LABSYS|HOSPITAL|EMR|FACILITY|20240315120000||ORU^R01|MSG001|P|2.5\r"
            "PID|1||P123456^^^MRN^MR||DOE^JANE^M||19850601|F|||456 OAK ST^^TESTCITY^CA^90210||555-0123\r"
            "OBR|1|||MICRO^Microbiology Culture^L||202403151000||||||||SPEC123^BLOOD^L||||||||20240315100000|||F\r"
            "OBX|1|ST|ORG^Organism^L||Staphylococcus aureus||||||F\r"
            "OBX|2|NM|MIC^Oxacillin MIC^L||1|mg/L|S|||F\r"
            "OBX|3|NM|MIC^Vancomycin MIC^L||2|mg/L|S|||F\r"
        )
    
    def _setup_malformed_hl7v2_state(self, params: Dict[str, Any]) -> str:
        """Set up malformed HL7v2 message state."""
        return (
            "MSH|^~\\&|LABSYS|HOSPITAL|EMR|FACILITY|20240315120000||ORU^R01|MSG002|P|2.5\r"
            "PID|1||P789012^^^MRN^MR||INVALID^PATIENT\r"
            # Missing required OBR segment
            "OBX|1|ST|ORG^Organism^L||Missing Breakpoint||||||F\r"
            "OBX|2|NM|MIC^Unknown Drug^L||INVALID|INVALID_UNIT|INVALID|||F"
        )
    
    def _setup_direct_input_state(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Set up direct classification input state."""
        return {
            "organism": "Escherichia coli",
            "antibiotic": "Ciprofloxacin",
            "method": "MIC",
            "mic_mg_L": 0.25,
            "specimenId": "DIRECT-001"
        }
    
    def _setup_invalid_input_state(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Set up invalid classification input state."""
        return {
            # Missing organism
            "antibiotic": "Unknown Drug",
            "method": "MIC"
            # Missing mic_mg_L value
        }
    
    def _create_fhir_patient(self, patient_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create FHIR Patient resource from patient data."""
        return {
            "resourceType": "Patient",
            "id": patient_data["id"],
            "identifier": [{"value": patient_data["mrn"]}],
            "name": [{"text": patient_data["name"]}],
            "gender": patient_data.get("gender"),
            "birthDate": patient_data.get("birth_date"),
            "active": patient_data.get("active", True)
        }
    
    def _create_fhir_specimen(self, specimen_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create FHIR Specimen resource from specimen data."""
        return {
            "resourceType": "Specimen",
            "id": specimen_data["id"],
            "subject": {"reference": f"Patient/{specimen_data['patient_id']}"},
            "type": {"text": specimen_data["type"]},
            "collection": {
                "collectedDateTime": specimen_data.get("collected_date")
            }
        }
    
    def _create_fhir_observation(self, obs_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create FHIR Observation resource from observation data."""
        return {
            "resourceType": "Observation",
            "id": obs_data["id"],
            "status": obs_data.get("status", "final"),
            "subject": {"reference": f"Patient/{obs_data['patient_id']}"},
            "specimen": {"reference": f"Specimen/{obs_data.get('specimen_id', '')}"},
            "valueQuantity": {
                "value": obs_data.get("value"),
                "unit": obs_data.get("unit")
            },
            "component": [
                {
                    "code": {"text": "Organism"},
                    "valueText": obs_data.get("organism")
                },
                {
                    "code": {"text": "Antibiotic"},
                    "valueText": obs_data.get("antibiotic")
                }
            ]
        }
    
    def _persist_state_to_database(self, state_name: str, state_data: Any):
        """Persist state data to test database."""
        try:
            with self.db_engine.connect() as conn:
                # Insert patients
                for patient_id, patient_data in self.db_state.patients.items():
                    conn.execute(
                        text("""
                            INSERT OR REPLACE INTO patients 
                            (id, mrn, name, gender, birth_date, active, metadata)
                            VALUES (:id, :mrn, :name, :gender, :birth_date, :active, :metadata)
                        """),
                        {
                            **patient_data,
                            "metadata": json.dumps({"state": state_name})
                        }
                    )
                
                # Insert specimens
                for specimen_id, specimen_data in self.db_state.specimens.items():
                    conn.execute(
                        text("""
                            INSERT OR REPLACE INTO specimens 
                            (id, patient_id, type, collected_date, status, metadata)
                            VALUES (:id, :patient_id, :type, :collected_date, :status, :metadata)
                        """),
                        {
                            **specimen_data,
                            "metadata": json.dumps({"state": state_name})
                        }
                    )
                
                # Insert observations
                for obs_id, obs_data in self.db_state.observations.items():
                    conn.execute(
                        text("""
                            INSERT OR REPLACE INTO observations 
                            (id, patient_id, specimen_id, organism, antibiotic, method, value, unit, status, metadata)
                            VALUES (:id, :patient_id, :specimen_id, :organism, :antibiotic, :method, :value, :unit, :status, :metadata)
                        """),
                        {
                            **obs_data,
                            "metadata": json.dumps({"state": state_name})
                        }
                    )
                
                conn.commit()
                
            logger.debug(f"State data persisted to database for: {state_name}")
            
        except Exception as e:
            logger.error(f"Failed to persist state to database: {e}")
            # Continue without database persistence for testing
    
    def _configure_rule_engine_for_state(self, state_name: str, params: Dict[str, Any]):
        """Configure rule engine for specific state."""
        try:
            if "IL-Core" in state_name:
                self._configure_il_core_rules()
            elif "US-Core" in state_name:
                self._configure_us_core_rules()
            elif "invalid organism" in state_name:
                self._configure_organism_validation_rules()
            
            # Apply custom breakpoint overrides if needed
            if params.get("breakpoint_overrides"):
                self.rule_state.breakpoint_overrides.update(params["breakpoint_overrides"])
                
        except Exception as e:
            logger.warning(f"Failed to configure rule engine for state '{state_name}': {e}")
    
    def _configure_il_core_rules(self):
        """Configure IL-Core specific validation rules."""
        self.rule_state.profile_rules["IL-Core"] = {
            "required_identifiers": ["IL-ID"],
            "required_fields": ["national_id"],
            "validation_strict": True,
            "hebrew_names_supported": True
        }
    
    def _configure_us_core_rules(self):
        """Configure US-Core specific validation rules."""
        self.rule_state.profile_rules["US-Core"] = {
            "required_identifiers": ["MR"],
            "required_fields": ["ssn"],
            "validation_strict": False,
            "english_names_required": True
        }
    
    def _configure_organism_validation_rules(self):
        """Configure organism validation rules."""
        self.rule_state.organism_rules = {
            "supported_organisms": [
                "112283007",  # Escherichia coli
                "3092008",    # Staphylococcus aureus
                "40886007"    # Klebsiella pneumoniae
            ],
            "validation_enabled": True
        }
    
    @asynccontextmanager
    async def async_state_context(self, state_name: str, params: Optional[Dict[str, Any]] = None) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Async context manager for provider state setup and cleanup.
        
        Args:
            state_name: Name of the provider state
            params: Additional state parameters
            
        Yields:
            State data for the scenario
        """
        state_data = None
        try:
            state_data = self.setup_provider_state(state_name, params)
            yield state_data
        finally:
            await self.async_cleanup_state(state_name)
    
    async def async_cleanup_state(self, state_name: str):
        """Asynchronously clean up provider state."""
        try:
            # Clean up async tasks
            for task_id, task in list(self.async_tasks.items()):
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                del self.async_tasks[task_id]
            
            # Clear state data
            self.db_state.clear()
            self.rule_state.clear()
            
            logger.debug(f"Async cleanup completed for state: {state_name}")
            
        except Exception as e:
            logger.error(f"Error during async state cleanup: {e}")
    
    def create_async_classification_task(self, task_id: str, classification_data: Dict[str, Any]) -> asyncio.Task:
        """
        Create an async classification task for testing.
        
        Args:
            task_id: Unique task identifier
            classification_data: Classification input data
            
        Returns:
            asyncio.Task: The created async task
        """
        async def mock_async_classification():
            # Simulate processing delay
            await asyncio.sleep(0.5)
            
            # Mock classification logic
            organism = classification_data.get("organism", "Unknown")
            antibiotic = classification_data.get("antibiotic", "Unknown")
            method = classification_data.get("method", "MIC")
            value = classification_data.get("mic_mg_L", 0)
            
            # Simple mock decision logic
            if value <= 1.0:
                decision = "S"
                reason = f"MIC {value} mg/L is <= susceptible breakpoint"
            elif value <= 4.0:
                decision = "I"
                reason = f"MIC {value} mg/L is in intermediate range"
            else:
                decision = "R"
                reason = f"MIC {value} mg/L is >= resistant breakpoint"
            
            result = {
                "task_id": task_id,
                "status": "completed",
                "organism": organism,
                "antibiotic": antibiotic,
                "method": method,
                "input": classification_data,
                "decision": decision,
                "reason": reason,
                "ruleVersion": self.rule_state.rules_version,
                "processed_at": time.time()
            }
            
            # Store result in classifications
            self.db_state.classifications[task_id] = result
            
            return result
        
        task = asyncio.create_task(mock_async_classification())
        self.async_tasks[task_id] = task
        
        logger.info(f"Async classification task created: {task_id}")
        return task
    
    def get_async_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        Get status of async classification task.
        
        Args:
            task_id: Task identifier
            
        Returns:
            Task status information
        """
        if task_id not in self.async_tasks:
            return {"task_id": task_id, "status": "not_found"}
        
        task = self.async_tasks[task_id]
        
        if task.done():
            if task.exception():
                return {
                    "task_id": task_id,
                    "status": "failed",
                    "error": str(task.exception())
                }
            else:
                return {
                    "task_id": task_id,
                    "status": "completed",
                    "result": task.result()
                }
        else:
            return {
                "task_id": task_id,
                "status": "processing"
            }
    
    def setup_webhook_mock(self, webhook_url: str, expected_payload: Optional[Dict[str, Any]] = None):
        """
        Set up webhook mock for verification result publishing.
        
        Args:
            webhook_url: URL to mock
            expected_payload: Expected webhook payload for validation
        """
        def mock_webhook(*args, **kwargs):
            webhook_call = {
                "url": webhook_url,
                "method": kwargs.get("method", "POST"),
                "headers": kwargs.get("headers", {}),
                "payload": kwargs.get("json", kwargs.get("data")),
                "timestamp": time.time()
            }
            
            self.webhook_history.append(webhook_call)
            
            # Validate payload if expected
            if expected_payload and webhook_call["payload"]:
                for key, expected_value in expected_payload.items():
                    if key not in webhook_call["payload"]:
                        logger.warning(f"Missing expected key in webhook payload: {key}")
                    elif webhook_call["payload"][key] != expected_value:
                        logger.warning(f"Unexpected value for {key}: got {webhook_call['payload'][key]}, expected {expected_value}")
            
            # Mock successful response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "received", "id": f"webhook-{len(self.webhook_history)}"}
            
            return mock_response
        
        # Apply mock patch
        patch_obj = patch('requests.post', side_effect=mock_webhook)
        self.mock_patches.append(patch_obj)
        patch_obj.start()
        
        logger.info(f"Webhook mock set up for: {webhook_url}")
    
    def cleanup(self):
        """Clean up all provider state resources."""
        try:
            # Stop all mock patches
            for patch_obj in self.mock_patches:
                patch_obj.stop()
            self.mock_patches.clear()
            
            # Cancel async tasks
            for task in self.async_tasks.values():
                if not task.done():
                    task.cancel()
            self.async_tasks.clear()
            
            # Clear state data
            self.db_state.clear()
            self.rule_state.clear()
            self.webhook_history.clear()
            
            # Close database connection
            if self.db_engine:
                self.db_engine.dispose()
            
            logger.info("Provider state manager cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


# Global instance for use in tests
provider_state_manager = ProviderStateManager()