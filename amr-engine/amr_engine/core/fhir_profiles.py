from __future__ import annotations

import logging
import json
from typing import Any, Dict, List, Optional, Set
from pathlib import Path
import httpx
from urllib.parse import urljoin

logger = logging.getLogger(__name__)


class FHIRProfileValidator:
    """FHIR Profile validation against standard and custom profiles."""
    
    def __init__(self, profile_registry_url: Optional[str] = None):
        self.profile_registry_url = profile_registry_url or "http://hl7.org/fhir"
        self.cached_profiles: Dict[str, Dict[str, Any]] = {}
        self.validation_errors: List[Dict[str, str]] = []
        self.validation_warnings: List[Dict[str, str]] = []
    
    async def validate_against_profile(
        self, 
        resource: Dict[str, Any], 
        profile_url: str
    ) -> bool:
        """Validate a FHIR resource against a specific profile."""
        self.validation_errors.clear()
        self.validation_warnings.clear()
        
        try:
            # Load profile definition
            profile = await self._load_profile(profile_url)
            if not profile:
                self.validation_errors.append({
                    "path": "/meta/profile",
                    "message": f"Could not load profile: {profile_url}",
                    "severity": "error"
                })
                return False
            
            # Validate resource against profile
            return self._validate_resource_structure(resource, profile)
            
        except Exception as e:
            logger.error(f"Profile validation failed: {e}")
            self.validation_errors.append({
                "path": "/",
                "message": f"Profile validation error: {str(e)}",
                "severity": "error"
            })
            return False
    
    async def _load_profile(self, profile_url: str) -> Optional[Dict[str, Any]]:
        """Load FHIR profile definition."""
        if profile_url in self.cached_profiles:
            return self.cached_profiles[profile_url]
        
        try:
            # First try standard FHIR profiles
            if profile_url.startswith("http://hl7.org/fhir/"):
                profile = await self._load_standard_profile(profile_url)
                if profile:
                    self.cached_profiles[profile_url] = profile
                    return profile
            
            # Try loading from custom registry
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(profile_url)
                if response.status_code == 200:
                    profile = response.json()
                    self.cached_profiles[profile_url] = profile
                    return profile
                    
        except Exception as e:
            logger.warning(f"Failed to load profile {profile_url}: {e}")
        
        return None
    
    async def _load_standard_profile(self, profile_url: str) -> Optional[Dict[str, Any]]:
        """Load standard FHIR profiles with built-in definitions."""
        # Built-in profile definitions for common AMR profiles
        standard_profiles = {
            "http://hl7.org/fhir/StructureDefinition/Observation": self._get_observation_profile(),
            "http://hl7.org/fhir/StructureDefinition/DiagnosticReport": self._get_diagnostic_report_profile(),
            "http://hl7.org/fhir/StructureDefinition/Patient": self._get_patient_profile(),
            "http://hl7.org/fhir/StructureDefinition/Specimen": self._get_specimen_profile(),
            "http://hl7.org/fhir/StructureDefinition/Bundle": self._get_bundle_profile(),
            # AMR-specific profiles
            "http://hl7.org/fhir/uv/laboratory/StructureDefinition/Observation-resultsMicroOrg": self._get_microbiology_observation_profile(),
            "http://hl7.org/fhir/uv/laboratory/StructureDefinition/Observation-resultsAst": self._get_ast_observation_profile(),
        }
        
        return standard_profiles.get(profile_url)
    
    def _get_observation_profile(self) -> Dict[str, Any]:
        """Get base Observation profile definition."""
        return {
            "resourceType": "StructureDefinition",
            "id": "Observation",
            "url": "http://hl7.org/fhir/StructureDefinition/Observation",
            "differential": {
                "element": [
                    {
                        "id": "Observation",
                        "path": "Observation"
                    },
                    {
                        "id": "Observation.status",
                        "path": "Observation.status",
                        "min": 1,
                        "max": "1",
                        "type": [{"code": "code"}],
                        "binding": {
                            "strength": "required",
                            "valueSet": "http://hl7.org/fhir/ValueSet/observation-status"
                        }
                    },
                    {
                        "id": "Observation.category",
                        "path": "Observation.category",
                        "min": 0,
                        "max": "*",
                        "type": [{"code": "CodeableConcept"}]
                    },
                    {
                        "id": "Observation.code",
                        "path": "Observation.code",
                        "min": 1,
                        "max": "1",
                        "type": [{"code": "CodeableConcept"}]
                    },
                    {
                        "id": "Observation.subject",
                        "path": "Observation.subject",
                        "min": 0,
                        "max": "1",
                        "type": [{"code": "Reference"}]
                    }
                ]
            }
        }
    
    def _get_microbiology_observation_profile(self) -> Dict[str, Any]:
        """Get microbiology-specific Observation profile."""
        return {
            "resourceType": "StructureDefinition",
            "id": "Observation-resultsMicroOrg",
            "url": "http://hl7.org/fhir/uv/laboratory/StructureDefinition/Observation-resultsMicroOrg",
            "differential": {
                "element": [
                    {
                        "id": "Observation",
                        "path": "Observation"
                    },
                    {
                        "id": "Observation.category",
                        "path": "Observation.category",
                        "min": 1,
                        "max": "*",
                        "fixedCodeableConcept": {
                            "coding": [{
                                "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                                "code": "laboratory"
                            }]
                        }
                    },
                    {
                        "id": "Observation.code",
                        "path": "Observation.code",
                        "binding": {
                            "strength": "preferred",
                            "valueSet": "http://hl7.org/fhir/uv/laboratory/ValueSet/micro-organism-codes"
                        }
                    },
                    {
                        "id": "Observation.valueCodeableConcept",
                        "path": "Observation.valueCodeableConcept",
                        "min": 1,
                        "max": "1",
                        "type": [{"code": "CodeableConcept"}],
                        "binding": {
                            "strength": "preferred", 
                            "valueSet": "http://hl7.org/fhir/uv/laboratory/ValueSet/micro-snomed-organisms"
                        }
                    },
                    {
                        "id": "Observation.specimen",
                        "path": "Observation.specimen",
                        "min": 1,
                        "max": "1",
                        "type": [{"code": "Reference", "targetProfile": ["http://hl7.org/fhir/StructureDefinition/Specimen"]}]
                    }
                ]
            }
        }
    
    def _get_ast_observation_profile(self) -> Dict[str, Any]:
        """Get AST-specific Observation profile."""
        return {
            "resourceType": "StructureDefinition",
            "id": "Observation-resultsAst", 
            "url": "http://hl7.org/fhir/uv/laboratory/StructureDefinition/Observation-resultsAst",
            "differential": {
                "element": [
                    {
                        "id": "Observation",
                        "path": "Observation"
                    },
                    {
                        "id": "Observation.category",
                        "path": "Observation.category",
                        "min": 1,
                        "max": "*",
                        "fixedCodeableConcept": {
                            "coding": [{
                                "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                                "code": "laboratory"
                            }]
                        }
                    },
                    {
                        "id": "Observation.code",
                        "path": "Observation.code",
                        "binding": {
                            "strength": "preferred",
                            "valueSet": "http://hl7.org/fhir/uv/laboratory/ValueSet/antimicrobial-susceptibility-codes"
                        }
                    },
                    {
                        "id": "Observation.valueQuantity",
                        "path": "Observation.valueQuantity",
                        "min": 0,
                        "max": "1",
                        "type": [{"code": "Quantity"}]
                    },
                    {
                        "id": "Observation.interpretation", 
                        "path": "Observation.interpretation",
                        "min": 0,
                        "max": "*",
                        "type": [{"code": "CodeableConcept"}],
                        "binding": {
                            "strength": "required",
                            "valueSet": "http://hl7.org/fhir/ValueSet/observation-interpretation"
                        }
                    },
                    {
                        "id": "Observation.method",
                        "path": "Observation.method",
                        "min": 0,
                        "max": "1",
                        "type": [{"code": "CodeableConcept"}]
                    },
                    {
                        "id": "Observation.derivedFrom",
                        "path": "Observation.derivedFrom",
                        "min": 1,
                        "max": "*",
                        "type": [{"code": "Reference"}]
                    }
                ]
            }
        }
    
    def _get_diagnostic_report_profile(self) -> Dict[str, Any]:
        """Get DiagnosticReport profile definition."""
        return {
            "resourceType": "StructureDefinition",
            "id": "DiagnosticReport",
            "url": "http://hl7.org/fhir/StructureDefinition/DiagnosticReport",
            "differential": {
                "element": [
                    {
                        "id": "DiagnosticReport.status",
                        "path": "DiagnosticReport.status", 
                        "min": 1,
                        "max": "1"
                    },
                    {
                        "id": "DiagnosticReport.category",
                        "path": "DiagnosticReport.category",
                        "min": 1,
                        "max": "*"
                    },
                    {
                        "id": "DiagnosticReport.code",
                        "path": "DiagnosticReport.code",
                        "min": 1,
                        "max": "1"
                    },
                    {
                        "id": "DiagnosticReport.subject",
                        "path": "DiagnosticReport.subject",
                        "min": 1,
                        "max": "1"
                    }
                ]
            }
        }
    
    def _get_patient_profile(self) -> Dict[str, Any]:
        """Get Patient profile definition."""
        return {
            "resourceType": "StructureDefinition", 
            "id": "Patient",
            "url": "http://hl7.org/fhir/StructureDefinition/Patient",
            "differential": {
                "element": [
                    {
                        "id": "Patient.identifier",
                        "path": "Patient.identifier",
                        "min": 0,
                        "max": "*"
                    }
                ]
            }
        }
    
    def _get_specimen_profile(self) -> Dict[str, Any]:
        """Get Specimen profile definition."""
        return {
            "resourceType": "StructureDefinition",
            "id": "Specimen",
            "url": "http://hl7.org/fhir/StructureDefinition/Specimen", 
            "differential": {
                "element": [
                    {
                        "id": "Specimen.type",
                        "path": "Specimen.type",
                        "min": 1,
                        "max": "1"
                    },
                    {
                        "id": "Specimen.subject",
                        "path": "Specimen.subject",
                        "min": 1,
                        "max": "1"
                    }
                ]
            }
        }
    
    def _get_bundle_profile(self) -> Dict[str, Any]:
        """Get Bundle profile definition."""
        return {
            "resourceType": "StructureDefinition",
            "id": "Bundle", 
            "url": "http://hl7.org/fhir/StructureDefinition/Bundle",
            "differential": {
                "element": [
                    {
                        "id": "Bundle.type",
                        "path": "Bundle.type",
                        "min": 1,
                        "max": "1"
                    }
                ]
            }
        }
    
    def _validate_resource_structure(self, resource: Dict[str, Any], profile: Dict[str, Any]) -> bool:
        """Validate resource structure against profile."""
        is_valid = True
        
        # Get differential elements from profile
        differential = profile.get("differential", {})
        elements = differential.get("element", [])
        
        for element in elements:
            element_path = element.get("path", "")
            element_id = element.get("id", "")
            
            # Skip root element
            if element_path == resource.get("resourceType"):
                continue
            
            # Parse element path
            path_parts = element_path.split(".")
            if len(path_parts) < 2:
                continue
            
            field_name = path_parts[-1]
            
            # Check cardinality
            min_occurs = element.get("min", 0)
            max_occurs = element.get("max", "*")
            
            field_value = resource.get(field_name)
            
            # Check minimum cardinality
            if min_occurs > 0:
                if field_value is None:
                    self.validation_errors.append({
                        "path": f"/{field_name}",
                        "message": f"Required field '{field_name}' is missing (min: {min_occurs})",
                        "severity": "error"
                    })
                    is_valid = False
                elif isinstance(field_value, list) and len(field_value) < min_occurs:
                    self.validation_errors.append({
                        "path": f"/{field_name}",
                        "message": f"Field '{field_name}' has {len(field_value)} items, minimum {min_occurs} required",
                        "severity": "error"
                    })
                    is_valid = False
            
            # Check maximum cardinality
            if max_occurs != "*" and isinstance(max_occurs, (int, str)):
                try:
                    max_int = int(max_occurs)
                    if isinstance(field_value, list) and len(field_value) > max_int:
                        self.validation_errors.append({
                            "path": f"/{field_name}",
                            "message": f"Field '{field_name}' has {len(field_value)} items, maximum {max_int} allowed",
                            "severity": "error"
                        })
                        is_valid = False
                except ValueError:
                    pass
            
            # Check data types
            element_types = element.get("type", [])
            if element_types and field_value is not None:
                is_valid &= self._validate_data_type(field_value, element_types, f"/{field_name}")
            
            # Check fixed values
            if "fixedCodeableConcept" in element and field_value:
                is_valid &= self._validate_fixed_codeable_concept(field_value, element["fixedCodeableConcept"], f"/{field_name}")
        
        return is_valid
    
    def _validate_data_type(self, value: Any, allowed_types: List[Dict[str, Any]], path: str) -> bool:
        """Validate field data type."""
        if not allowed_types:
            return True
        
        type_codes = [t.get("code") for t in allowed_types]
        
        # Basic type validation
        valid = False
        for type_code in type_codes:
            if type_code == "string" and isinstance(value, str):
                valid = True
                break
            elif type_code == "code" and isinstance(value, str):
                valid = True
                break
            elif type_code == "CodeableConcept" and isinstance(value, dict):
                valid = True
                break
            elif type_code == "Reference" and isinstance(value, dict) and "reference" in value:
                valid = True
                break
            elif type_code == "Quantity" and isinstance(value, dict):
                valid = True
                break
        
        if not valid:
            self.validation_errors.append({
                "path": path,
                "message": f"Invalid data type. Expected one of: {type_codes}",
                "severity": "error"
            })
        
        return valid
    
    def _validate_fixed_codeable_concept(self, value: Any, fixed_value: Dict[str, Any], path: str) -> bool:
        """Validate fixed CodeableConcept value."""
        if not isinstance(value, dict):
            return False
        
        fixed_coding = fixed_value.get("coding", [])
        value_coding = value.get("coding", [])
        
        if not value_coding:
            self.validation_errors.append({
                "path": f"{path}/coding",
                "message": "Missing required coding",
                "severity": "error"
            })
            return False
        
        # Check if any coding matches fixed coding
        for fixed_code in fixed_coding:
            found_match = False
            for value_code in value_coding:
                if (value_code.get("system") == fixed_code.get("system") and
                    value_code.get("code") == fixed_code.get("code")):
                    found_match = True
                    break
            
            if not found_match:
                self.validation_warnings.append({
                    "path": f"{path}/coding",
                    "message": f"Expected coding {fixed_code.get('system')}|{fixed_code.get('code')}",
                    "severity": "warning"
                })
        
        return True


# Global profile validator instance
fhir_profile_validator = FHIRProfileValidator()