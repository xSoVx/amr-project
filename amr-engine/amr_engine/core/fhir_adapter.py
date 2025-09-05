from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .exceptions import FHIRValidationError
from .schemas import ClassificationInput

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


def parse_bundle_or_observations(payload: Any) -> List[ClassificationInput]:
    # Accept Bundle or array of Observations
    if isinstance(payload, dict) and payload.get("resourceType") == "Bundle":
        entries = payload.get("entry")
        if not isinstance(entries, list):
            raise FHIRValidationError("Bundle.entry must be an array")
        observations = [e.get("resource") for e in entries if isinstance(e, dict) and isinstance(e.get("resource"), dict) and e.get("resource", {}).get("resourceType") == "Observation"]
    elif isinstance(payload, list):
        observations = [o for o in payload if isinstance(o, dict) and o.get("resourceType") == "Observation"]
    elif isinstance(payload, dict) and payload.get("resourceType") == "Observation":
        observations = [payload]
    else:
        raise FHIRValidationError("Payload must be a FHIR Bundle or Observation(s)")

    results: List[ClassificationInput] = []
    for obs in observations:
        code = obs.get("code") or {}
        value = obs.get("valueQuantity") or None
        method = _parse_method(obs, value)
        specimen_ref = (obs.get("specimen") or {}).get("reference")
        subject_ref = (obs.get("subject") or {}).get("reference")
        notes = obs.get("note")
        organism_name, features = _parse_organism_from_note(notes)

        # Infer antibiotic from code display (or text)
        antibiotic_name: Optional[str] = None
        coding = code.get("coding")
        if isinstance(coding, list) and coding:
            antibiotic_name = coding[0].get("display") or None
        if not antibiotic_name and isinstance(code.get("text"), str):
            antibiotic_name = code.get("text")
        if antibiotic_name:
            # Normalize to drug name without bracket text
            antibiotic_name = antibiotic_name.split("[")[0].strip()

        mic = None
        disc = None
        if value and method == "MIC":
            mic = value.get("value")
        if value and method == "DISC":
            disc = value.get("value")

        if method == "MIC" and mic is None:
            # Allow through to classify as RR with reason later, but ensure structure OK
            pass
        if method == "DISC" and disc is None:
            pass

        if not antibiotic_name:
            raise FHIRValidationError("Observation.code missing or lacks antibiotic display")

        results.append(
            ClassificationInput(
                organism=organism_name,
                antibiotic=antibiotic_name,
                method=method,  # may be None; classifier returns RR if incomplete
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

