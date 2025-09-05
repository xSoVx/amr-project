from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .exceptions import FHIRValidationError
from .schemas import ClassificationInput
from .fhir_resources import FHIRValidator, FHIRResourceExtractor
from .terminology import terminology_service
from .tracing import get_tracer

logger = logging.getLogger(__name__)


def _parse_method(obs: Dict[str, Any], value: Dict[str, Any] | None) -> Optional[str]:
    method = obs.get("method", {})
    if isinstance(method, dict):
        coding = method.get("coding")
        if isinstance(coding, list) and coding:
            code = coding[0].get("code")
            if code in ("MIC", "DISC"):
                return code
        text = method.get("text")
        if text in ("MIC", "DISC", "DISK", "DISK_DIFFUSION"):
            return "DISC" if text.startswith("DIS") else "MIC"
    if value and isinstance(value, dict) and value.get("unit"):
        unit = value.get("unit")
        if unit == "mg/L":
            return "MIC"
        if unit == "mm":
            return "DISC"
    return None


def _parse_organism_from_note(notes: List[Dict[str, Any]] | None) -> tuple[Optional[str], dict]:
    features: dict = {}
    name: Optional[str] = None
    if not notes:
        return None, features
    for n in notes:
        t = n.get("text") if isinstance(n, dict) else None
        if not t:
            continue
        # Example: "E. coli; ESBL=false"
        parts = [p.strip() for p in t.split(";")]
        if parts:
            if not name:
                name = parts[0] if parts[0] else None
        for p in parts[1:]:
            if "=" in p:
                k, v = [x.strip() for x in p.split("=", 1)]
                if v.lower() in ("true", "false"):
                    features[k.lower()] = True if v.lower() == "true" else False
                else:
                    features[k.lower()] = v
    return name, features


async def _parse_organism_from_bundle(obs_data: Dict[str, Any], extractor: FHIRResourceExtractor) -> tuple[Optional[str], dict]:
    """Enhanced organism parsing with SNOMED validation and derivedFrom resolution."""
    features: dict = {}
    organism_name: Optional[str] = None
    organism_snomed: Optional[str] = None
    
    # First try to get organism from notes (existing method)
    notes = obs_data.get("note")
    if notes:
        organism_name, features = _parse_organism_from_note(notes)
    
    # Try to resolve derivedFrom references to find organism observations
    derived_from = obs_data.get("derivedFrom", [])
    for ref in derived_from:
        ref_id = ref.get("reference", "").split("/")[-1] if ref.get("reference") else None
        if ref_id and ref_id in extractor.observations:
            parent_obs = extractor.observations[ref_id]
            parent_data = parent_obs.model_dump()
            
            # Check if this is an organism identification observation
            code = parent_data.get("code", {})
            code_text = code.get("text", "").lower()
            
            if "organism" in code_text or "identified" in code_text:
                # Extract organism from valueCodeableConcept
                value_concept = parent_data.get("valueCodeableConcept", {})
                if value_concept:
                    # Try SNOMED coding first
                    for coding in value_concept.get("coding", []):
                        if coding.get("system") == "http://snomed.info/sct":
                            organism_snomed = coding.get("code")
                            # Validate SNOMED code
                            validation = await terminology_service.validate_code(
                                system=coding.get("system"),
                                code=coding.get("code"),
                                display=coding.get("display")
                            )
                            if validation.valid:
                                organism_name = validation.display or coding.get("display")
                                features["organism_snomed"] = organism_snomed
                                break
                    
                    # Fallback to text
                    if not organism_name:
                        organism_name = value_concept.get("text")
    
    # Normalize organism name
    if organism_name:
        organism_name = terminology_service.normalize_organism_name(organism_name)
    
    return organism_name, features


async def _parse_antibiotic_from_code(code: Dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
    """Enhanced antibiotic parsing with ATC code validation."""
    antibiotic_name: Optional[str] = None
    antibiotic_atc: Optional[str] = None
    
    # Try to get from LOINC or local coding first
    for coding in code.get("coding", []):
        display = coding.get("display")
        if display:
            # Check for ATC codes
            if coding.get("system") and "atc" in coding.get("system", "").lower():
                antibiotic_atc = coding.get("code")
            antibiotic_name = display
            break
    
    # Fallback to text
    if not antibiotic_name:
        antibiotic_name = code.get("text")
    
    if antibiotic_name:
        # Clean antibiotic name (remove [Susceptibility] etc.)
        antibiotic_name = antibiotic_name.split("[")[0].strip()
        # Common antibiotic mappings to ATC codes
        atc_mappings = {
            "ciprofloxacin": "J01MA02",
            "ceftriaxone": "J01DD04", 
            "ceftazidime": "J01DD02",
            "oxacillin": "J01CF04",
            "piperacillin": "J01CA12",
            "meropenem": "J01DH02",
            "imipenem": "J01DH01",
            "vancomycin": "J01XA01",
            "gentamicin": "J01GB03",
            "amikacin": "J01GB06"
        }
        
        if not antibiotic_atc:
            antibiotic_atc = atc_mappings.get(antibiotic_name.lower())
    
    return antibiotic_name, antibiotic_atc


async def _parse_enhanced_method(obs_data: Dict[str, Any], value: Optional[Dict[str, Any]]) -> Optional[str]:
    """Enhanced method parsing with better detection."""
    # Use existing method parsing
    method = _parse_method(obs_data, value)
    
    # Enhanced detection from code text
    if not method:
        code = obs_data.get("code", {})
        code_text = code.get("text", "").lower()
        
        if "mic" in code_text:
            method = "MIC"
        elif any(term in code_text for term in ["disk", "disc", "diffusion"]):
            method = "DISC"
        elif "zone" in code_text:
            method = "DISC"
    
    return method


@get_tracer().trace_fhir_operation(resource_type="Bundle", operation="parse")
async def parse_bundle_or_observations(payload: Any) -> List[ClassificationInput]:
    """Enhanced FHIR parser with comprehensive validation and SNOMED support."""
    tracer = get_tracer()
    validator = FHIRValidator()
    extractor = FHIRResourceExtractor()
    
    # Enhanced Bundle validation
    if isinstance(payload, dict) and payload.get("resourceType") == "Bundle":
        # Validate Bundle structure
        is_valid = await validator.validate_bundle(payload)
        if not is_valid:
            error_details = "; ".join([f"{e['path']}: {e['message']}" for e in validator.errors[:3]])
            raise FHIRValidationError(f"Bundle validation failed: {error_details}", issues=validator.errors)
        
        # Extract resources from Bundle
        if not extractor.extract_from_bundle(payload):
            raise FHIRValidationError("Failed to extract resources from Bundle")
        
        observations = list(extractor.observations.values())
        
    elif isinstance(payload, list):
        observations = []
        for obs_data in payload:
            if isinstance(obs_data, dict) and obs_data.get("resourceType") == "Observation":
                # Validate individual observation
                if not validator._validate_observation(obs_data, "/"):
                    error_details = "; ".join([f"{e['path']}: {e['message']}" for e in validator.errors])
                    raise FHIRValidationError(f"Observation validation failed: {error_details}")
                observations.append(obs_data)
                
    elif isinstance(payload, dict) and payload.get("resourceType") == "Observation":
        if not validator._validate_observation(payload, "/"):
            error_details = "; ".join([f"{e['path']}: {e['message']}" for e in validator.errors])
            raise FHIRValidationError(f"Observation validation failed: {error_details}")
        observations = [payload]
    else:
        raise FHIRValidationError("Payload must be a FHIR Bundle or Observation(s)")

    results: List[ClassificationInput] = []
    for obs in observations:
        obs_data = obs if isinstance(obs, dict) else obs.model_dump()
        
        code = obs_data.get("code") or {}
        value = obs_data.get("valueQuantity") or None
        method = _parse_method(obs_data, value)
        specimen_ref = (obs_data.get("specimen") or {}).get("reference")
        subject_ref = (obs_data.get("subject") or {}).get("reference")
        notes = obs_data.get("note")
        
        # Enhanced organism extraction with SNOMED validation
        organism_name, features = await _parse_organism_from_bundle(obs_data, extractor)
        
        # Enhanced antibiotic extraction with SNOMED validation
        antibiotic_name, antibiotic_snomed = await _parse_antibiotic_from_code(code)
        
        # Enhanced method detection
        method = await _parse_enhanced_method(obs_data, value)
        
        mic = None
        disc = None
        if value and method == "MIC":
            mic = value.get("value")
            # Validate MIC units
            unit = value.get("unit") or value.get("code")
            if unit and unit not in ["mg/L", "mg/ml", "μg/ml"]:
                logger.warning(f"Non-standard MIC unit: {unit}")
                
        if value and method == "DISC":
            disc = value.get("value")
            # Validate disc units
            unit = value.get("unit") or value.get("code")
            if unit and unit not in ["mm"]:
                logger.warning(f"Non-standard disc unit: {unit}")

        # Enhanced validation
        if method == "MIC" and mic is None:
            raise FHIRValidationError("MIC method requires valueQuantity with numeric value")
        if method == "DISC" and disc is None:
            raise FHIRValidationError("Disc method requires valueQuantity with numeric value")

        if not antibiotic_name:
            raise FHIRValidationError("Observation.code missing or lacks antibiotic display")

        results.append(
            ClassificationInput(
                organism=organism_name,
                organism_snomed=features.get("organism_snomed"),
                antibiotic=antibiotic_name,
                antibiotic_atc=antibiotic_snomed,
                method=method,
                mic_mg_L=mic,
                disc_zone_mm=disc,
                specimenId=specimen_ref,
                patientId=subject_ref,
                features=features,
            )
        )
    
    if not results:
        raise FHIRValidationError("No valid Observation resources found")
    return results

