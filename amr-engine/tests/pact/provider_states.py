"""
Provider states for Pact contract testing.

This module defines the provider states that set up specific scenarios
for testing the AMR classification microservice API endpoints.
"""

from typing import Dict, Any, List
import json
import logging

logger = logging.getLogger(__name__)


class ProviderStates:
    """Manages provider states for AMR classification service Pact testing."""
    
    @staticmethod
    def healthy_patient_data() -> Dict[str, Any]:
        """
        Provider state: healthy patient data with valid AMR test results.
        
        Returns complete FHIR Bundle with Patient, Specimen, and Observation
        resources containing valid antimicrobial susceptibility test data.
        """
        return {
            "resourceType": "Bundle",
            "id": "healthy-patient-bundle",
            "type": "collection",
            "entry": [
                {
                    "resource": {
                        "resourceType": "Patient",
                        "id": "patient-healthy",
                        "identifier": [
                            {
                                "use": "usual",
                                "type": {
                                    "coding": [
                                        {
                                            "system": "http://terminology.hl7.org/CodeSystem/v2-0203",
                                            "code": "MR"
                                        }
                                    ]
                                },
                                "value": "HEALTHY001"
                            }
                        ],
                        "name": [
                            {
                                "family": "TestPatient",
                                "given": ["Healthy", "A"]
                            }
                        ],
                        "gender": "female",
                        "birthDate": "1990-01-01"
                    }
                },
                {
                    "resource": {
                        "resourceType": "Specimen",
                        "id": "specimen-healthy",
                        "identifier": [
                            {
                                "value": "SPEC-HEALTHY-001"
                            }
                        ],
                        "type": {
                            "coding": [
                                {
                                    "system": "http://snomed.info/sct",
                                    "code": "119365002",
                                    "display": "Blood specimen"
                                }
                            ]
                        },
                        "subject": {
                            "reference": "Patient/patient-healthy"
                        },
                        "collection": {
                            "collectedDateTime": "2024-03-15T09:00:00Z"
                        }
                    }
                },
                {
                    "resource": {
                        "resourceType": "Observation",
                        "id": "organism-healthy",
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
                            "reference": "Patient/patient-healthy"
                        },
                        "specimen": {
                            "reference": "Specimen/specimen-healthy"
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
                        "id": "ampicillin-susceptible",
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
                        "subject": {
                            "reference": "Patient/patient-healthy"
                        },
                        "specimen": {
                            "reference": "Specimen/specimen-healthy"
                        },
                        "valueQuantity": {
                            "value": 4.0,
                            "unit": "mg/L"
                        }
                    }
                }
            ]
        }
    
    @staticmethod
    def invalid_fhir_bundle() -> Dict[str, Any]:
        """
        Provider state: invalid FHIR bundle with missing required elements.
        
        Returns a malformed FHIR Bundle that should trigger validation errors.
        """
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
                        "subject": {
                            "reference": "Patient/nonexistent"
                        },
                        "valueQuantity": {
                            # Missing required value
                            "unit": "mg/L"
                        }
                    }
                }
            ]
        }
    
    @staticmethod
    def missing_organism_data() -> Dict[str, Any]:
        """
        Provider state: data with missing organism information.
        
        Returns classification input without organism data that should
        trigger validation errors.
        """
        return {
            "resourceType": "Bundle",
            "id": "missing-organism-bundle",
            "type": "collection",
            "entry": [
                {
                    "resource": {
                        "resourceType": "Patient",
                        "id": "patient-missing-org",
                        "identifier": [
                            {
                                "value": "MISSING-ORG-001"
                            }
                        ]
                    }
                },
                {
                    "resource": {
                        "resourceType": "Observation",
                        "id": "ampicillin-no-organism",
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
                        "subject": {
                            "reference": "Patient/patient-missing-org"
                        },
                        "valueQuantity": {
                            "value": 8.0,
                            "unit": "mg/L"
                        }
                        # Missing organism information in components
                    }
                }
            ]
        }
    
    @staticmethod
    def get_il_core_patient_data() -> Dict[str, Any]:
        """
        Provider state: IL-Core compliant patient data.
        
        Returns FHIR Bundle compliant with Israeli healthcare standards.
        """
        return {
            "resourceType": "Bundle",
            "id": "il-core-patient-bundle",
            "meta": {
                "profile": ["http://fhir.health.gov.il/StructureDefinition/il-core-bundle"]
            },
            "type": "collection",
            "entry": [
                {
                    "resource": {
                        "resourceType": "Patient",
                        "id": "patient-il-core",
                        "meta": {
                            "profile": ["http://fhir.health.gov.il/StructureDefinition/il-core-patient"]
                        },
                        "identifier": [
                            {
                                "use": "usual",
                                "type": {
                                    "coding": [
                                        {
                                            "system": "http://fhir.health.gov.il/cs/il-core-identifier-type",
                                            "code": "IL-ID"
                                        }
                                    ]
                                },
                                "system": "http://fhir.health.gov.il/identifier/il-national-id",
                                "value": "123456789"
                            }
                        ],
                        "name": [
                            {
                                "family": "כהן",
                                "given": ["דוד"]
                            }
                        ],
                        "gender": "male",
                        "birthDate": "1985-05-15"
                    }
                },
                {
                    "resource": {
                        "resourceType": "Observation",
                        "id": "observation-il-core",
                        "meta": {
                            "profile": ["http://fhir.health.gov.il/StructureDefinition/il-core-observation-lab"]
                        },
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
                        "subject": {
                            "reference": "Patient/patient-il-core"
                        },
                        "valueQuantity": {
                            "value": 2.0,
                            "unit": "mg/L"
                        },
                        "component": [
                            {
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
                            }
                        ]
                    }
                }
            ]
        }
    
    @staticmethod
    def get_us_core_patient_data() -> Dict[str, Any]:
        """
        Provider state: US-Core compliant patient data.
        
        Returns FHIR Bundle compliant with US healthcare interoperability standards.
        """
        return {
            "resourceType": "Bundle",
            "id": "us-core-patient-bundle",
            "meta": {
                "profile": ["http://hl7.org/fhir/us/core/StructureDefinition/us-core-bundle"]
            },
            "type": "collection",
            "entry": [
                {
                    "resource": {
                        "resourceType": "Patient",
                        "id": "patient-us-core",
                        "meta": {
                            "profile": ["http://hl7.org/fhir/us/core/StructureDefinition/us-core-patient"]
                        },
                        "identifier": [
                            {
                                "use": "usual",
                                "type": {
                                    "coding": [
                                        {
                                            "system": "http://terminology.hl7.org/CodeSystem/v2-0203",
                                            "code": "MR",
                                            "display": "Medical Record Number"
                                        }
                                    ]
                                },
                                "system": "http://hospital.example.com",
                                "value": "USCORE001"
                            }
                        ],
                        "name": [
                            {
                                "family": "Smith",
                                "given": ["John", "Q"],
                                "use": "official"
                            }
                        ],
                        "gender": "male",
                        "birthDate": "1975-12-31",
                        "address": [
                            {
                                "line": ["123 Healthcare Ave"],
                                "city": "Boston",
                                "state": "MA",
                                "postalCode": "02101",
                                "country": "US"
                            }
                        ]
                    }
                },
                {
                    "resource": {
                        "resourceType": "Observation",
                        "id": "observation-us-core",
                        "meta": {
                            "profile": ["http://hl7.org/fhir/us/core/StructureDefinition/us-core-observation-lab"]
                        },
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
                                    "code": "33747-0",
                                    "display": "Cefotaxime [Susceptibility] by Minimum inhibitory concentration (MIC)"
                                }
                            ]
                        },
                        "subject": {
                            "reference": "Patient/patient-us-core"
                        },
                        "valueQuantity": {
                            "value": 0.5,
                            "unit": "mg/L"
                        },
                        "component": [
                            {
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
                                            "code": "40886007",
                                            "display": "Klebsiella pneumoniae"
                                        }
                                    ]
                                }
                            }
                        ]
                    }
                }
            ]
        }
    
    @staticmethod
    def get_healthy_hl7v2_message() -> str:
        """
        Provider state: healthy HL7v2 message with valid AMR data.
        
        Returns well-formed HL7v2 message containing antimicrobial
        susceptibility test results.
        """
        return (
            "MSH|^~\\&|LABSYS|HOSPITAL|EMR|FACILITY|20240315120000||ORU^R01|MSG001|P|2.5\r"
            "PID|1||P123456^^^MRN^MR||DOE^JANE^M||19850601|F|||456 OAK ST^^TESTCITY^CA^90210||555-0123\r"
            "OBR|1|||MICRO^Microbiology Culture^L||202403151000||||||||SPEC123^BLOOD^L||||||||20240315100000|||F\r"
            "OBX|1|ST|ORG^Organism^L||Staphylococcus aureus||||||F\r"
            "OBX|2|NM|MIC^Oxacillin MIC^L||1|mg/L|S|||F\r"
            "OBX|3|NM|MIC^Vancomycin MIC^L||2|mg/L|S|||F\r"
            "OBX|4|NM|DISC^Clindamycin Disc^L||22|mm|S|||F"
        )
    
    @staticmethod
    def get_malformed_hl7v2_message() -> str:
        """
        Provider state: malformed HL7v2 message for error testing.
        
        Returns HL7v2 message with structural errors.
        """
        return (
            "MSH|^~\\&|LABSYS|HOSPITAL|EMR|FACILITY|20240315120000||ORU^R01|MSG002|P|2.5\r"
            "PID|1||P789012^^^MRN^MR||INVALID^PATIENT\r"
            # Missing required OBR segment
            "OBX|1|ST|ORG^Organism^L||Missing Breakpoint||||||F\r"
            "OBX|2|NM|MIC^Unknown Drug^L||INVALID|INVALID_UNIT|INVALID|||F"
        )
    
    @staticmethod
    def get_direct_classification_input() -> Dict[str, Any]:
        """
        Provider state: direct classification input for raw JSON endpoint.
        
        Returns valid ClassificationInput data structure.
        """
        return {
            "organism": "Escherichia coli",
            "antibiotic": "Ciprofloxacin",
            "method": "MIC",
            "mic_mg_L": 0.25,
            "specimenId": "DIRECT-001"
        }
    
    @staticmethod
    def get_invalid_classification_input() -> Dict[str, Any]:
        """
        Provider state: invalid classification input for error testing.
        
        Returns invalid ClassificationInput missing required fields.
        """
        return {
            # Missing organism
            "antibiotic": "Unknown Drug",
            "method": "MIC"
            # Missing mic_mg_L value
        }


def setup_provider_state(state_name: str) -> Any:
    """
    Setup function for Pact provider state management.
    
    Args:
        state_name: Name of the provider state to set up
        
    Returns:
        Data structure appropriate for the requested state
        
    Raises:
        ValueError: If state_name is not recognized
    """
    states = ProviderStates()
    
    state_mapping = {
        "healthy patient data": states.healthy_patient_data,
        "invalid FHIR bundle": states.invalid_fhir_bundle,
        "missing organism data": states.missing_organism_data,
        "IL-Core patient data": states.get_il_core_patient_data,
        "US-Core patient data": states.get_us_core_patient_data,
        "healthy HL7v2 message": states.get_healthy_hl7v2_message,
        "malformed HL7v2 message": states.get_malformed_hl7v2_message,
        "direct classification input": states.get_direct_classification_input,
        "invalid classification input": states.get_invalid_classification_input,
    }
    
    if state_name not in state_mapping:
        raise ValueError(f"Unknown provider state: {state_name}")
    
    logger.info(f"Setting up provider state: {state_name}")
    return state_mapping[state_name]()