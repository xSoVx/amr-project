from __future__ import annotations

import logging
import json
from typing import Any, Dict, List, Optional, Set
from pathlib import Path
import httpx
from urllib.parse import urljoin

from ..config import ProfilePack

logger = logging.getLogger(__name__)


class FHIRProfileValidator:
    """FHIR Profile validation against standard and custom profiles."""
    
    def __init__(self, profile_pack: ProfilePack = "Base", profile_registry_url: Optional[str] = None):
        self.profile_pack = profile_pack
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
        """Load standard FHIR profiles with built-in definitions based on profile pack."""
        # Base profiles available in all packs
        base_profiles = {
            "http://hl7.org/fhir/StructureDefinition/Observation": self._get_observation_profile(),
            "http://hl7.org/fhir/StructureDefinition/DiagnosticReport": self._get_diagnostic_report_profile(),
            "http://hl7.org/fhir/StructureDefinition/Patient": self._get_patient_profile(),
            "http://hl7.org/fhir/StructureDefinition/Specimen": self._get_specimen_profile(),
            "http://hl7.org/fhir/StructureDefinition/Bundle": self._get_bundle_profile(),
            # AMR-specific profiles
            "http://hl7.org/fhir/uv/laboratory/StructureDefinition/Observation-resultsMicroOrg": self._get_microbiology_observation_profile(),
            "http://hl7.org/fhir/uv/laboratory/StructureDefinition/Observation-resultsAst": self._get_ast_observation_profile(),
        }
        
        # Profile pack specific profiles
        pack_profiles = {}
        if self.profile_pack == "IL-Core":
            pack_profiles.update(self._get_il_core_profiles())
        elif self.profile_pack == "US-Core":
            pack_profiles.update(self._get_us_core_profiles())
        elif self.profile_pack == "IPS":
            pack_profiles.update(self._get_ips_profiles())
        
        # Merge base and pack-specific profiles
        all_profiles = {**base_profiles, **pack_profiles}
        return all_profiles.get(profile_url)
    
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
        """Validate resource structure against profile with enhanced validation."""
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
            
            # Parse element path and extract nested field references
            is_valid &= self._validate_element_against_resource(element, resource, element_path)
        
        return is_valid

    def _validate_element_against_resource(self, element: Dict[str, Any], resource: Dict[str, Any], element_path: str) -> bool:
        """Validate a single element against resource data."""
        is_valid = True
        
        # Parse element path
        path_parts = element_path.split(".")
        if len(path_parts) < 2:
            return True
        
        # Navigate to nested field value
        field_value, actual_path = self._get_nested_field_value(resource, path_parts[1:])
        
        # Check cardinality
        min_occurs = element.get("min", 0) 
        max_occurs = element.get("max", "*")
        must_support = element.get("mustSupport", False)
        
        # Validate minimum cardinality
        if min_occurs > 0:
            if field_value is None:
                self.validation_errors.append({
                    "path": actual_path,
                    "message": f"Required field at '{actual_path}' is missing (min: {min_occurs})",
                    "severity": "error"
                })
                is_valid = False
            elif isinstance(field_value, list) and len(field_value) < min_occurs:
                self.validation_errors.append({
                    "path": actual_path,
                    "message": f"Field at '{actual_path}' has {len(field_value)} items, minimum {min_occurs} required",
                    "severity": "error"
                })
                is_valid = False
        
        # Validate maximum cardinality 
        if max_occurs != "*" and isinstance(max_occurs, (int, str)):
            try:
                max_int = int(max_occurs)
                if isinstance(field_value, list) and len(field_value) > max_int:
                    self.validation_errors.append({
                        "path": actual_path,
                        "message": f"Field at '{actual_path}' has {len(field_value)} items, maximum {max_int} allowed",
                        "severity": "error"
                    })
                    is_valid = False
            except ValueError:
                pass
        
        # Validate mustSupport elements
        if must_support and field_value is None:
            self.validation_warnings.append({
                "path": actual_path,
                "message": f"MustSupport element at '{actual_path}' should be present for interoperability",
                "severity": "warning"
            })
        
        # Validate data types
        element_types = element.get("type", [])
        if element_types and field_value is not None:
            is_valid &= self._validate_data_type(field_value, element_types, actual_path)
        
        # Validate value bindings (terminologies)
        binding = element.get("binding")
        if binding and field_value is not None:
            is_valid &= self._validate_terminology_binding(field_value, binding, actual_path)
        
        # Validate fixed values
        if "fixedCodeableConcept" in element and field_value:
            is_valid &= self._validate_fixed_codeable_concept(field_value, element["fixedCodeableConcept"], actual_path)
        
        # Validate constraints and conditions
        conditions = element.get("condition", [])
        if conditions and field_value is not None:
            is_valid &= self._validate_element_conditions(field_value, conditions, actual_path)
        
        return is_valid

    def _get_nested_field_value(self, resource: Dict[str, Any], path_parts: List[str]) -> tuple[Any, str]:
        """Navigate nested field path and return value and actual path."""
        current = resource
        actual_path = ""
        
        for i, part in enumerate(path_parts):
            if current is None:
                return None, actual_path
            
            actual_path += f"/{part}"
            
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, list) and len(current) > 0:
                # For arrays, check the first element
                current = current[0].get(part) if isinstance(current[0], dict) else None
            else:
                return None, actual_path
        
        return current, actual_path

    def _validate_terminology_binding(self, value: Any, binding: Dict[str, Any], path: str) -> bool:
        """Validate terminology bindings including LOINC, SNOMED CT."""
        is_valid = True
        strength = binding.get("strength", "required")
        value_set_url = binding.get("valueSet", "")
        
        if not isinstance(value, dict) or "coding" not in value:
            if strength == "required":
                self.validation_errors.append({
                    "path": path,
                    "message": f"Required terminology binding missing coding for {value_set_url}",
                    "severity": "error"
                })
                is_valid = False
            return is_valid
        
        coding = value.get("coding", [])
        if not coding:
            if strength == "required":
                self.validation_errors.append({
                    "path": f"{path}/coding",
                    "message": f"Required terminology binding missing coding for {value_set_url}",
                    "severity": "error" 
                })
                is_valid = False
            return is_valid
        
        # Validate specific code systems
        valid_found = False
        for code in coding:
            system = code.get("system", "")
            code_value = code.get("code", "")
            
            # LOINC validation (AMR-specific codes)
            if "loinc" in value_set_url.lower() or system == "http://loinc.org":
                valid_found |= self._validate_loinc_code(code_value, system, path)
            
            # SNOMED CT validation
            elif "snomed" in value_set_url.lower() or system == "http://snomed.info/sct":
                valid_found |= self._validate_snomed_code(code_value, system, path)
                
            # US Core specific value sets
            elif "us-core" in value_set_url:
                valid_found |= self._validate_us_core_codes(code_value, system, value_set_url, path)
                
            # IL Core specific value sets
            elif "il-core" in value_set_url or "fhir.health.gov.il" in value_set_url:
                valid_found |= self._validate_il_core_codes(code_value, system, value_set_url, path)
            
            else:
                # Generic validation - just check system and code are present
                if system and code_value:
                    valid_found = True
        
        if not valid_found and strength == "required":
            self.validation_errors.append({
                "path": f"{path}/coding",
                "message": f"No valid codes found for required value set {value_set_url}",
                "severity": "error"
            })
            is_valid = False
        elif not valid_found and strength == "extensible":
            self.validation_warnings.append({
                "path": f"{path}/coding", 
                "message": f"No codes from preferred value set {value_set_url}, should use standard terms when available",
                "severity": "warning"
            })
        
        return is_valid

    def _validate_loinc_code(self, code: str, system: str, path: str) -> bool:
        """Validate LOINC codes, especially AMR-relevant ones."""
        # Key AMR LOINC codes from QA report
        amr_loinc_codes = {
            "18769-0": "Microbial susceptibility tests Set",
            "6932-8": "Susceptibility interpreted based on breakpoint (nominal)", 
            "33747-0": "Susceptibility interpretation of antimicrobial"
        }
        
        if system != "http://loinc.org":
            self.validation_warnings.append({
                "path": f"{path}/coding",
                "message": f"Expected LOINC system 'http://loinc.org', got '{system}'",
                "severity": "warning"
            })
        
        if code in amr_loinc_codes:
            return True
        
        # Basic LOINC format validation (numeric-numeric)
        if "-" in code and len(code.split("-")) == 2:
            try:
                parts = code.split("-")
                int(parts[0])
                int(parts[1])
                return True
            except ValueError:
                pass
        
        self.validation_warnings.append({
            "path": f"{path}/coding",
            "message": f"LOINC code '{code}' format may be invalid or not AMR-relevant",
            "severity": "warning"
        })
        return False

    def _validate_snomed_code(self, code: str, system: str, path: str) -> bool:
        """Validate SNOMED CT codes."""
        if system != "http://snomed.info/sct":
            self.validation_warnings.append({
                "path": f"{path}/coding",
                "message": f"Expected SNOMED CT system 'http://snomed.info/sct', got '{system}'", 
                "severity": "warning"
            })
        
        # Basic SNOMED code validation (numeric)
        if code.isdigit() and len(code) >= 6:
            return True
        
        self.validation_warnings.append({
            "path": f"{path}/coding",
            "message": f"SNOMED CT code '{code}' format may be invalid",
            "severity": "warning"
        })
        return False

    def _validate_us_core_codes(self, code: str, system: str, value_set_url: str, path: str) -> bool:
        """Validate US Core specific codes."""
        # Common US Core systems and sample codes
        us_core_systems = {
            "http://terminology.hl7.org/CodeSystem/observation-category": ["laboratory", "vital-signs"],
            "http://terminology.hl7.org/CodeSystem/v2-0074": ["LAB", "RAD"],
            "http://hl7.org/fhir/administrative-gender": ["male", "female", "other", "unknown"]
        }
        
        if system in us_core_systems:
            if code in us_core_systems[system]:
                return True
            self.validation_warnings.append({
                "path": f"{path}/coding",
                "message": f"Code '{code}' may not be valid for US Core system '{system}'",
                "severity": "warning"
            })
        
        return True  # Allow other codes

    def _validate_il_core_codes(self, code: str, system: str, value_set_url: str, path: str) -> bool:
        """Validate IL Core specific codes.""" 
        # Israeli identifier systems
        il_identifier_systems = [
            "http://fhir.health.gov.il/identifier/il-national-id",
            "http://fhir.health.gov.il/identifier/il-passport-number"
        ]
        
        if "identifier-systems" in value_set_url and system in il_identifier_systems:
            return True
        
        return True  # Allow other IL Core codes

    def _validate_element_conditions(self, value: Any, conditions: List[str], path: str) -> bool:
        """Validate element-specific conditions."""
        is_valid = True
        
        for condition in conditions:
            if condition == "us-core-2":
                # US Core constraint: must have value[x] OR dataAbsentReason
                # This would need access to sibling elements - simplified for now
                pass
        
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
    
    def _get_il_core_profiles(self) -> Dict[str, Dict[str, Any]]:
        """Get IL-Core (Israeli Core) specific profiles with comprehensive validation."""
        return {
            "http://fhir.health.gov.il/StructureDefinition/il-core-patient": {
                "resourceType": "StructureDefinition",
                "id": "il-core-patient",
                "url": "http://fhir.health.gov.il/StructureDefinition/il-core-patient",
                "differential": {
                    "element": [
                        {
                            "id": "Patient.extension:statistical-area",
                            "path": "Patient.extension",
                            "sliceName": "statistical-area",
                            "min": 0,
                            "max": "1",
                            "type": [{"code": "Extension"}],
                            "profile": ["http://fhir.health.gov.il/StructureDefinition/ext-statistical-area"]
                        },
                        {
                            "id": "Patient.identifier",
                            "path": "Patient.identifier",
                            "min": 1,
                            "max": "*",
                            "mustSupport": True
                        },
                        {
                            "id": "Patient.identifier.system",
                            "path": "Patient.identifier.system",
                            "min": 1,
                            "max": "1",
                            "mustSupport": True,
                            "binding": {
                                "strength": "required",
                                "valueSet": "http://fhir.health.gov.il/ValueSet/il-core-identifier-systems"
                            }
                        },
                        {
                            "id": "Patient.identifier.value",
                            "path": "Patient.identifier.value",
                            "min": 1,
                            "max": "1",
                            "mustSupport": True
                        },
                        {
                            "id": "Patient.name",
                            "path": "Patient.name",
                            "min": 1,
                            "max": "*",
                            "mustSupport": True
                        },
                        {
                            "id": "Patient.name.family",
                            "path": "Patient.name.family",
                            "min": 1,
                            "max": "1",
                            "mustSupport": True
                        },
                        {
                            "id": "Patient.name.given",
                            "path": "Patient.name.given",
                            "min": 1,
                            "max": "*",
                            "mustSupport": True
                        },
                        {
                            "id": "Patient.gender",
                            "path": "Patient.gender",
                            "min": 1,
                            "max": "1",
                            "mustSupport": True,
                            "binding": {
                                "strength": "required",
                                "valueSet": "http://hl7.org/fhir/ValueSet/administrative-gender"
                            }
                        },
                        {
                            "id": "Patient.birthDate",
                            "path": "Patient.birthDate",
                            "min": 1,
                            "max": "1",
                            "mustSupport": True
                        },
                        {
                            "id": "Patient.address",
                            "path": "Patient.address",
                            "min": 0,
                            "max": "*",
                            "mustSupport": True
                        },
                        {
                            "id": "Patient.telecom",
                            "path": "Patient.telecom",
                            "min": 0,
                            "max": "*",
                            "mustSupport": True
                        }
                    ]
                }
            },
            "http://fhir.health.gov.il/StructureDefinition/il-core-observation": {
                "resourceType": "StructureDefinition", 
                "id": "il-core-observation",
                "url": "http://fhir.health.gov.il/StructureDefinition/il-core-observation",
                "differential": {
                    "element": [
                        {
                            "id": "Observation.identifier",
                            "path": "Observation.identifier",
                            "min": 0,
                            "max": "*",
                            "mustSupport": True
                        },
                        {
                            "id": "Observation.status",
                            "path": "Observation.status",
                            "min": 1,
                            "max": "1",
                            "mustSupport": True,
                            "binding": {
                                "strength": "required",
                                "valueSet": "http://hl7.org/fhir/ValueSet/observation-status"
                            }
                        },
                        {
                            "id": "Observation.category",
                            "path": "Observation.category",
                            "min": 1,
                            "max": "*",
                            "mustSupport": True
                        },
                        {
                            "id": "Observation.code",
                            "path": "Observation.code",
                            "min": 1,
                            "max": "1",
                            "mustSupport": True,
                            "binding": {
                                "strength": "preferred",
                                "valueSet": "http://fhir.health.gov.il/ValueSet/il-core-observation-codes"
                            }
                        },
                        {
                            "id": "Observation.subject",
                            "path": "Observation.subject",
                            "min": 1,
                            "max": "1",
                            "mustSupport": True,
                            "type": [{"code": "Reference", "targetProfile": ["http://fhir.health.gov.il/StructureDefinition/il-core-patient"]}]
                        },
                        {
                            "id": "Observation.effectiveDateTime",
                            "path": "Observation.effectiveDateTime",
                            "min": 0,
                            "max": "1",
                            "mustSupport": True
                        },
                        {
                            "id": "Observation.performer",
                            "path": "Observation.performer",
                            "min": 0,
                            "max": "*",
                            "mustSupport": True
                        }
                    ]
                }
            },
            "http://fhir.health.gov.il/StructureDefinition/il-core-diagnosticreport": {
                "resourceType": "StructureDefinition",
                "id": "il-core-diagnosticreport",
                "url": "http://fhir.health.gov.il/StructureDefinition/il-core-diagnosticreport",
                "differential": {
                    "element": [
                        {
                            "id": "DiagnosticReport.identifier",
                            "path": "DiagnosticReport.identifier",
                            "min": 0,
                            "max": "*",
                            "mustSupport": True
                        },
                        {
                            "id": "DiagnosticReport.status",
                            "path": "DiagnosticReport.status",
                            "min": 1,
                            "max": "1",
                            "mustSupport": True,
                            "binding": {
                                "strength": "required",
                                "valueSet": "http://hl7.org/fhir/ValueSet/diagnostic-report-status"
                            }
                        },
                        {
                            "id": "DiagnosticReport.category",
                            "path": "DiagnosticReport.category",
                            "min": 1,
                            "max": "*",
                            "mustSupport": True
                        },
                        {
                            "id": "DiagnosticReport.code",
                            "path": "DiagnosticReport.code",
                            "min": 1,
                            "max": "1",
                            "mustSupport": True,
                            "binding": {
                                "strength": "preferred",
                                "valueSet": "http://fhir.health.gov.il/ValueSet/il-core-diagnosticreport-codes"
                            }
                        },
                        {
                            "id": "DiagnosticReport.subject",
                            "path": "DiagnosticReport.subject",
                            "min": 1,
                            "max": "1",
                            "mustSupport": True,
                            "type": [{"code": "Reference", "targetProfile": ["http://fhir.health.gov.il/StructureDefinition/il-core-patient"]}]
                        },
                        {
                            "id": "DiagnosticReport.effectiveDateTime",
                            "path": "DiagnosticReport.effectiveDateTime",
                            "min": 1,
                            "max": "1",
                            "mustSupport": True
                        },
                        {
                            "id": "DiagnosticReport.issued",
                            "path": "DiagnosticReport.issued",
                            "min": 1,
                            "max": "1",
                            "mustSupport": True
                        },
                        {
                            "id": "DiagnosticReport.performer",
                            "path": "DiagnosticReport.performer",
                            "min": 1,
                            "max": "*",
                            "mustSupport": True
                        },
                        {
                            "id": "DiagnosticReport.result",
                            "path": "DiagnosticReport.result",
                            "min": 0,
                            "max": "*",
                            "mustSupport": True,
                            "type": [{"code": "Reference", "targetProfile": ["http://fhir.health.gov.il/StructureDefinition/il-core-observation"]}]
                        }
                    ]
                }
            }
        }
    
    def _get_us_core_profiles(self) -> Dict[str, Dict[str, Any]]:
        """Get US-Core specific profiles with comprehensive validation."""
        return {
            "http://hl7.org/fhir/us/core/StructureDefinition/us-core-patient": {
                "resourceType": "StructureDefinition",
                "id": "us-core-patient",
                "url": "http://hl7.org/fhir/us/core/StructureDefinition/us-core-patient",
                "differential": {
                    "element": [
                        {
                            "id": "Patient.extension:race",
                            "path": "Patient.extension",
                            "sliceName": "race",
                            "min": 0,
                            "max": "1",
                            "type": [{"code": "Extension"}],
                            "profile": ["http://hl7.org/fhir/us/core/StructureDefinition/us-core-race"]
                        },
                        {
                            "id": "Patient.extension:ethnicity", 
                            "path": "Patient.extension",
                            "sliceName": "ethnicity",
                            "min": 0,
                            "max": "1",
                            "type": [{"code": "Extension"}],
                            "profile": ["http://hl7.org/fhir/us/core/StructureDefinition/us-core-ethnicity"]
                        },
                        {
                            "id": "Patient.identifier",
                            "path": "Patient.identifier",
                            "min": 1,
                            "max": "*",
                            "mustSupport": True
                        },
                        {
                            "id": "Patient.identifier.system",
                            "path": "Patient.identifier.system",
                            "min": 1,
                            "max": "1",
                            "mustSupport": True
                        },
                        {
                            "id": "Patient.identifier.value",
                            "path": "Patient.identifier.value", 
                            "min": 1,
                            "max": "1",
                            "mustSupport": True
                        },
                        {
                            "id": "Patient.name",
                            "path": "Patient.name",
                            "min": 1,
                            "max": "*",
                            "mustSupport": True
                        },
                        {
                            "id": "Patient.name.family",
                            "path": "Patient.name.family",
                            "min": 1,
                            "max": "1",
                            "mustSupport": True
                        },
                        {
                            "id": "Patient.name.given",
                            "path": "Patient.name.given",
                            "min": 0,
                            "max": "*",
                            "mustSupport": True
                        },
                        {
                            "id": "Patient.gender",
                            "path": "Patient.gender",
                            "min": 1,
                            "max": "1",
                            "mustSupport": True,
                            "binding": {
                                "strength": "required",
                                "valueSet": "http://hl7.org/fhir/ValueSet/administrative-gender"
                            }
                        },
                        {
                            "id": "Patient.birthDate",
                            "path": "Patient.birthDate",
                            "min": 0,
                            "max": "1",
                            "mustSupport": True
                        },
                        {
                            "id": "Patient.address",
                            "path": "Patient.address",
                            "min": 0,
                            "max": "*",
                            "mustSupport": True
                        },
                        {
                            "id": "Patient.telecom",
                            "path": "Patient.telecom",
                            "min": 0,
                            "max": "*",
                            "mustSupport": True
                        }
                    ]
                }
            },
            "http://hl7.org/fhir/us/core/StructureDefinition/us-core-observation-lab": {
                "resourceType": "StructureDefinition",
                "id": "us-core-observation-lab", 
                "url": "http://hl7.org/fhir/us/core/StructureDefinition/us-core-observation-lab",
                "differential": {
                    "element": [
                        {
                            "id": "Observation.status",
                            "path": "Observation.status",
                            "min": 1,
                            "max": "1",
                            "mustSupport": True,
                            "binding": {
                                "strength": "required",
                                "valueSet": "http://hl7.org/fhir/ValueSet/observation-status"
                            }
                        },
                        {
                            "id": "Observation.category",
                            "path": "Observation.category",
                            "min": 1,
                            "max": "*",
                            "mustSupport": True,
                            "fixedCodeableConcept": {
                                "coding": [{
                                    "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                                    "code": "laboratory",
                                    "display": "Laboratory"
                                }]
                            }
                        },
                        {
                            "id": "Observation.code",
                            "path": "Observation.code",
                            "min": 1,
                            "max": "1",
                            "mustSupport": True,
                            "binding": {
                                "strength": "extensible",
                                "valueSet": "http://hl7.org/fhir/us/core/ValueSet/us-core-observation-value"
                            }
                        },
                        {
                            "id": "Observation.subject",
                            "path": "Observation.subject",
                            "min": 1,
                            "max": "1",
                            "mustSupport": True,
                            "type": [{"code": "Reference", "targetProfile": ["http://hl7.org/fhir/us/core/StructureDefinition/us-core-patient"]}]
                        },
                        {
                            "id": "Observation.effectiveDateTime",
                            "path": "Observation.effectiveDateTime",
                            "min": 1,
                            "max": "1",
                            "mustSupport": True
                        },
                        {
                            "id": "Observation.valueQuantity",
                            "path": "Observation.valueQuantity",
                            "min": 0,
                            "max": "1",
                            "mustSupport": True,
                            "condition": ["us-core-2"]
                        },
                        {
                            "id": "Observation.valueCodeableConcept",
                            "path": "Observation.valueCodeableConcept",
                            "min": 0,
                            "max": "1", 
                            "mustSupport": True,
                            "condition": ["us-core-2"]
                        },
                        {
                            "id": "Observation.dataAbsentReason",
                            "path": "Observation.dataAbsentReason",
                            "min": 0,
                            "max": "1",
                            "mustSupport": True,
                            "condition": ["us-core-2"]
                        }
                    ]
                }
            },
            "http://hl7.org/fhir/us/core/StructureDefinition/us-core-diagnosticreport-lab": {
                "resourceType": "StructureDefinition",
                "id": "us-core-diagnosticreport-lab",
                "url": "http://hl7.org/fhir/us/core/StructureDefinition/us-core-diagnosticreport-lab",
                "differential": {
                    "element": [
                        {
                            "id": "DiagnosticReport.status",
                            "path": "DiagnosticReport.status",
                            "min": 1,
                            "max": "1",
                            "mustSupport": True
                        },
                        {
                            "id": "DiagnosticReport.category",
                            "path": "DiagnosticReport.category",
                            "min": 1,
                            "max": "*",
                            "mustSupport": True,
                            "fixedCodeableConcept": {
                                "coding": [{
                                    "system": "http://terminology.hl7.org/CodeSystem/v2-0074",
                                    "code": "LAB",
                                    "display": "Laboratory"
                                }]
                            }
                        },
                        {
                            "id": "DiagnosticReport.code",
                            "path": "DiagnosticReport.code",
                            "min": 1,
                            "max": "1",
                            "mustSupport": True,
                            "binding": {
                                "strength": "extensible",
                                "valueSet": "http://hl7.org/fhir/us/core/ValueSet/us-core-diagnosticreport-lab-codes"
                            }
                        },
                        {
                            "id": "DiagnosticReport.subject",
                            "path": "DiagnosticReport.subject",
                            "min": 1,
                            "max": "1",
                            "mustSupport": True,
                            "type": [{"code": "Reference", "targetProfile": ["http://hl7.org/fhir/us/core/StructureDefinition/us-core-patient"]}]
                        },
                        {
                            "id": "DiagnosticReport.effectiveDateTime",
                            "path": "DiagnosticReport.effectiveDateTime",
                            "min": 1,
                            "max": "1",
                            "mustSupport": True
                        },
                        {
                            "id": "DiagnosticReport.issued",
                            "path": "DiagnosticReport.issued",
                            "min": 1,
                            "max": "1",
                            "mustSupport": True
                        },
                        {
                            "id": "DiagnosticReport.performer",
                            "path": "DiagnosticReport.performer",
                            "min": 1,
                            "max": "*",
                            "mustSupport": True
                        },
                        {
                            "id": "DiagnosticReport.result",
                            "path": "DiagnosticReport.result",
                            "min": 0,
                            "max": "*",
                            "mustSupport": True,
                            "type": [{"code": "Reference", "targetProfile": ["http://hl7.org/fhir/us/core/StructureDefinition/us-core-observation-lab"]}]
                        }
                    ]
                }
            }
        }
    
    def _get_ips_profiles(self) -> Dict[str, Dict[str, Any]]:
        """Get IPS (International Patient Summary) specific profiles."""
        return {
            "http://hl7.org/fhir/uv/ips/StructureDefinition/Patient-uv-ips": {
                "resourceType": "StructureDefinition",
                "id": "Patient-uv-ips",
                "url": "http://hl7.org/fhir/uv/ips/StructureDefinition/Patient-uv-ips",
                "differential": {
                    "element": [
                        {
                            "id": "Patient.identifier",
                            "path": "Patient.identifier",
                            "min": 0,
                            "max": "*"
                        },
                        {
                            "id": "Patient.name",
                            "path": "Patient.name",
                            "min": 1,
                            "max": "*"
                        },
                        {
                            "id": "Patient.gender",
                            "path": "Patient.gender",
                            "min": 1,
                            "max": "1"
                        },
                        {
                            "id": "Patient.birthDate",
                            "path": "Patient.birthDate",
                            "min": 0,
                            "max": "1"
                        }
                    ]
                }
            },
            "http://hl7.org/fhir/uv/ips/StructureDefinition/Observation-results-uv-ips": {
                "resourceType": "StructureDefinition",
                "id": "Observation-results-uv-ips",
                "url": "http://hl7.org/fhir/uv/ips/StructureDefinition/Observation-results-uv-ips",
                "differential": {
                    "element": [
                        {
                            "id": "Observation.status",
                            "path": "Observation.status",
                            "min": 1,
                            "max": "1"
                        },
                        {
                            "id": "Observation.category",
                            "path": "Observation.category",
                            "min": 1,
                            "max": "*"
                        },
                        {
                            "id": "Observation.code",
                            "path": "Observation.code",
                            "min": 1,
                            "max": "1"
                        },
                        {
                            "id": "Observation.subject",
                            "path": "Observation.subject",
                            "min": 1,
                            "max": "1"
                        },
                        {
                            "id": "Observation.effectiveDateTime",
                            "path": "Observation.effectiveDateTime",
                            "min": 0,
                            "max": "1"
                        },
                        {
                            "id": "Observation.performer",
                            "path": "Observation.performer",
                            "min": 0,
                            "max": "*"
                        }
                    ]
                }
            }
        }


    async def validate_bundle_against_profile_pack(self, bundle: Dict[str, Any]) -> Dict[str, Any]:
        """Validate entire FHIR Bundle against selected profile pack."""
        validation_results = {
            "bundle_valid": True,
            "profile_pack": self.profile_pack,
            "total_resources": 0,
            "valid_resources": 0,
            "invalid_resources": 0,
            "resource_results": [],
            "summary_errors": [],
            "summary_warnings": []
        }
        
        # Validate bundle structure first
        if bundle.get("resourceType") != "Bundle":
            validation_results["bundle_valid"] = False
            validation_results["summary_errors"].append({
                "path": "/resourceType",
                "message": "Expected Bundle resourceType",
                "severity": "error"
            })
            return validation_results
        
        entries = bundle.get("entry", [])
        validation_results["total_resources"] = len(entries)
        
        for i, entry in enumerate(entries):
            resource = entry.get("resource", {})
            resource_type = resource.get("resourceType", "")
            
            # Determine profile URL based on resource type and profile pack
            profile_url = self._get_profile_url_for_resource(resource_type)
            
            if profile_url:
                # Validate against specific profile
                is_valid = await self.validate_against_profile(resource, profile_url)
                
                resource_result = {
                    "index": i,
                    "resource_type": resource_type,
                    "profile_url": profile_url,
                    "valid": is_valid,
                    "errors": self.validation_errors.copy(),
                    "warnings": self.validation_warnings.copy()
                }
                
                validation_results["resource_results"].append(resource_result)
                validation_results["summary_errors"].extend(self.validation_errors)
                validation_results["summary_warnings"].extend(self.validation_warnings)
                
                if is_valid:
                    validation_results["valid_resources"] += 1
                else:
                    validation_results["invalid_resources"] += 1
                    validation_results["bundle_valid"] = False
            else:
                # Resource type not covered by profile pack
                validation_results["resource_results"].append({
                    "index": i,
                    "resource_type": resource_type,
                    "profile_url": None,
                    "valid": True,
                    "errors": [],
                    "warnings": [{"message": f"No {self.profile_pack} profile available for {resource_type}"}]
                })
                validation_results["valid_resources"] += 1
        
        return validation_results
    
    def _get_profile_url_for_resource(self, resource_type: str) -> Optional[str]:
        """Get appropriate profile URL based on resource type and profile pack."""
        profile_mappings = {
            "US-Core": {
                "Patient": "http://hl7.org/fhir/us/core/StructureDefinition/us-core-patient",
                "Observation": "http://hl7.org/fhir/us/core/StructureDefinition/us-core-observation-lab",
                "DiagnosticReport": "http://hl7.org/fhir/us/core/StructureDefinition/us-core-diagnosticreport-lab"
            },
            "IL-Core": {
                "Patient": "http://fhir.health.gov.il/StructureDefinition/il-core-patient",
                "Observation": "http://fhir.health.gov.il/StructureDefinition/il-core-observation",
                "DiagnosticReport": "http://fhir.health.gov.il/StructureDefinition/il-core-diagnosticreport"
            },
            "IPS": {
                "Patient": "http://hl7.org/fhir/uv/ips/StructureDefinition/Patient-uv-ips",
                "Observation": "http://hl7.org/fhir/uv/ips/StructureDefinition/Observation-results-uv-ips"
            },
            "Base": {
                "Patient": "http://hl7.org/fhir/StructureDefinition/Patient",
                "Observation": "http://hl7.org/fhir/StructureDefinition/Observation",
                "DiagnosticReport": "http://hl7.org/fhir/StructureDefinition/DiagnosticReport",
                "Bundle": "http://hl7.org/fhir/StructureDefinition/Bundle",
                "Specimen": "http://hl7.org/fhir/StructureDefinition/Specimen"
            }
        }
        
        pack_profiles = profile_mappings.get(self.profile_pack, {})
        return pack_profiles.get(resource_type)

    def get_validation_summary(self) -> Dict[str, Any]:
        """Get comprehensive validation summary."""
        total_issues = len(self.validation_errors) + len(self.validation_warnings)
        
        return {
            "profile_pack": self.profile_pack,
            "validation_status": "passed" if len(self.validation_errors) == 0 else "failed",
            "total_issues": total_issues,
            "errors": len(self.validation_errors),
            "warnings": len(self.validation_warnings),
            "error_details": self.validation_errors,
            "warning_details": self.validation_warnings,
            "recommendations": self._get_validation_recommendations()
        }
    
    def _get_validation_recommendations(self) -> List[str]:
        """Generate validation improvement recommendations."""
        recommendations = []
        
        if len(self.validation_errors) > 0:
            recommendations.append("Fix validation errors before production deployment")
        
        if len(self.validation_warnings) > 5:
            recommendations.append("Consider addressing validation warnings for better interoperability")
        
        # Check for specific issues
        error_messages = [err.get("message", "") for err in self.validation_errors]
        
        if any("LOINC" in msg for msg in error_messages):
            recommendations.append("Ensure proper LOINC codes for laboratory observations (18769-0, 6932-8, 33747-0)")
        
        if any("SNOMED" in msg for msg in error_messages):
            recommendations.append("Verify SNOMED CT codes for organism and antimicrobial terms")
        
        if any("mustSupport" in msg.lower() for msg in [w.get("message", "") for w in self.validation_warnings]):
            recommendations.append("Include mustSupport elements for better profile compliance")
        
        if self.profile_pack in ["US-Core", "IL-Core"] and len(self.validation_warnings) > 0:
            recommendations.append(f"Review {self.profile_pack} implementation guide for complete compliance")
        
        return recommendations


# Global profile validator instance
fhir_profile_validator = FHIRProfileValidator()