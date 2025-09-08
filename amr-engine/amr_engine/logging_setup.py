import json
import logging
import re
import sys
import time
import uuid
from typing import Any, Dict, List

from .config import get_settings


class JsonFormatter(logging.Formatter):
    """JSON formatter with PII redaction for healthcare data."""
    
    def __init__(self):
        super().__init__()
        # Patterns for identifying patient/specimen identifiers
        self.redaction_patterns = [
            # Patient ID patterns
            (re.compile(r'(?i)\b(?:patient[_-]?id|patientid|pt[_-]?id|mrn)\s*[=:]\s*["\']?([^"\s,}]+)', re.IGNORECASE), 'patient_id'),
            # Specimen ID patterns  
            (re.compile(r'(?i)\b(?:specimen[_-]?id|specimenid|sample[_-]?id|sampleid|spec[_-]?id)\s*[=:]\s*["\']?([^"\s,}]+)', re.IGNORECASE), 'specimen_id'),
            # Generic ID patterns that might be PII
            (re.compile(r'(?i)\b(?:subject[_-]?id|subjectid)\s*[=:]\s*["\']?([^"\s,}]+)', re.IGNORECASE), 'subject_id'),
            # FHIR reference patterns
            (re.compile(r'(?i)"reference"\s*:\s*"(Patient/[^"]+)"', re.IGNORECASE), 'patient_reference'),
            (re.compile(r'(?i)"reference"\s*:\s*"(Specimen/[^"]+)"', re.IGNORECASE), 'specimen_reference'),
            # National ID patterns (adjust as needed for your region)
            (re.compile(r'\b\d{9}\b'), 'national_id'),  # 9-digit IDs
            (re.compile(r'\b\d{11}\b'), 'national_id'),  # 11-digit IDs
        ]
    
    def format(self, record: logging.LogRecord) -> str:  # type: ignore[override]
        payload: Dict[str, Any] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "message": self._redact_sensitive_data(record.getMessage()),
        }
        
        # Process extra fields with redaction
        for key, value in getattr(record, "extra", {}).items():
            if isinstance(value, str):
                payload[key] = self._redact_sensitive_data(value)
            elif isinstance(value, dict):
                payload[key] = self._redact_dict(value)
            else:
                payload[key] = value
        
        if record.exc_info:
            exc_text = self.formatException(record.exc_info)
            payload["exc_info"] = self._redact_sensitive_data(exc_text)
        
        return json.dumps(payload, ensure_ascii=False)
    
    def _redact_sensitive_data(self, text: str) -> str:
        """Redact sensitive patient/specimen identifiers from text."""
        if not isinstance(text, str):
            return text
        
        redacted_text = text
        for pattern, field_type in self.redaction_patterns:
            # Replace matches with redacted placeholders
            matches = pattern.findall(redacted_text)
            for match in matches:
                if isinstance(match, tuple):
                    # For patterns with groups, take the first group
                    identifier = match[0] if match else ""
                else:
                    identifier = match
                
                if identifier:
                    # Create a hash-based redacted identifier for traceability
                    import hashlib
                    redacted_id = f"[REDACTED_{field_type.upper()}_{hashlib.md5(identifier.encode()).hexdigest()[:8]}]"
                    redacted_text = redacted_text.replace(identifier, redacted_id)
        
        return redacted_text
    
    def _redact_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively redact sensitive data from dictionary structures."""
        redacted_dict = {}
        
        for key, value in data.items():
            key_lower = key.lower()
            
            # Check if key indicates sensitive data
            if any(sensitive in key_lower for sensitive in ['patient', 'specimen', 'subject', 'mrn', 'ssn']):
                if isinstance(value, str) and value:
                    # Hash the sensitive value
                    import hashlib
                    redacted_value = f"[REDACTED_{hashlib.md5(str(value).encode()).hexdigest()[:8]}]"
                    redacted_dict[key] = redacted_value
                else:
                    redacted_dict[key] = "[REDACTED]"
            elif isinstance(value, str):
                redacted_dict[key] = self._redact_sensitive_data(value)
            elif isinstance(value, dict):
                redacted_dict[key] = self._redact_dict(value)
            elif isinstance(value, list):
                redacted_dict[key] = [
                    self._redact_dict(item) if isinstance(item, dict)
                    else self._redact_sensitive_data(item) if isinstance(item, str)
                    else item
                    for item in value
                ]
            else:
                redacted_dict[key] = value
        
        return redacted_dict


def setup_logging() -> None:
    settings = get_settings()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))


def request_id() -> str:
    return uuid.uuid4().hex

