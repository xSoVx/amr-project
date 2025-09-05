"""
Structured error taxonomy for AMR Classification Engine.

Implements error code taxonomy as recommended in the AMR Unified System
documentation to provide actionable error details for triage and debugging.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class ErrorCategory(str, Enum):
    """High-level error categories for the AMR system."""
    INGEST = "INGEST"
    CLASSIFY = "CLASSIFY"  
    TERM = "TERM"
    PACK = "PACK"
    VALID = "VALID"
    AUTH = "AUTH"
    CONFIG = "CONFIG"
    SYSTEM = "SYSTEM"


class ErrorSeverity(str, Enum):
    """Error severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AMRErrorCode(str, Enum):
    """
    Structured error codes for AMR Classification Engine.
    
    Format: {CATEGORY}_{SPECIFIC_CODE}
    Following AMR Unified System recommendations for actionable error taxonomy.
    """
    
    # Ingestion errors (INGEST_xx)
    INGEST_INVALID_HL7 = "INGEST_001"
    INGEST_MISSING_SEGMENT = "INGEST_002"
    INGEST_INVALID_FHIR = "INGEST_003"
    INGEST_MISSING_RESOURCE = "INGEST_004"
    INGEST_DUPLICATE_MESSAGE = "INGEST_005"
    INGEST_UNSUPPORTED_FORMAT = "INGEST_006"
    
    # Classification errors (CLASSIFY_xx)  
    CLASSIFY_NO_RULES_FOUND = "CLASSIFY_001"
    CLASSIFY_MISSING_ORGANISM = "CLASSIFY_002"
    CLASSIFY_MISSING_ANTIBIOTIC = "CLASSIFY_003"
    CLASSIFY_INVALID_METHOD = "CLASSIFY_004"
    CLASSIFY_MISSING_VALUE = "CLASSIFY_005"
    CLASSIFY_RULE_EVALUATION_FAILED = "CLASSIFY_006"
    CLASSIFY_INTRINSIC_RESISTANCE = "CLASSIFY_007"
    CLASSIFY_COMBINATION_THERAPY = "CLASSIFY_008"
    
    # Terminology errors (TERM_xx)
    TERM_UNMAPPED_ORGANISM = "TERM_001"
    TERM_UNMAPPED_ANTIBIOTIC = "TERM_002"
    TERM_UNMAPPED_TEST_CODE = "TERM_003"
    TERM_SERVICE_UNAVAILABLE = "TERM_004"
    TERM_INVALID_CODE_SYSTEM = "TERM_005"
    TERM_VERSION_MISMATCH = "TERM_006"
    
    # Profile pack errors (PACK_xx)
    PACK_NOT_FOUND = "PACK_001"
    PACK_VERSION_NOT_FOUND = "PACK_002"
    PACK_INVALID_STRUCTURE = "PACK_003"
    PACK_DOWNLOAD_FAILED = "PACK_004"
    PACK_SIGNATURE_INVALID = "PACK_005"
    PACK_CONFLICT_RESOLUTION = "PACK_006"
    
    # Validation errors (VALID_xx)
    VALID_STRUCTURE_DEFINITION_FAILED = "VALID_001"
    VALID_VALUE_SET_BINDING_FAILED = "VALID_002"
    VALID_CARDINALITY_VIOLATION = "VALID_003"
    VALID_REQUIRED_ELEMENT_MISSING = "VALID_004"
    VALID_INVALID_DATA_TYPE = "VALID_005"
    VALID_PROFILE_NOT_SUPPORTED = "VALID_006"
    
    # Authentication/Authorization errors (AUTH_xx)
    AUTH_INVALID_TOKEN = "AUTH_001"
    AUTH_TOKEN_EXPIRED = "AUTH_002"
    AUTH_INSUFFICIENT_SCOPE = "AUTH_003"
    AUTH_TENANT_ACCESS_DENIED = "AUTH_004"
    AUTH_ADMIN_REQUIRED = "AUTH_005"
    
    # Configuration errors (CONFIG_xx)
    CONFIG_MISSING_REQUIRED = "CONFIG_001"
    CONFIG_INVALID_FORMAT = "CONFIG_002"
    CONFIG_FILE_NOT_FOUND = "CONFIG_003"
    CONFIG_RULES_LOAD_FAILED = "CONFIG_004"
    CONFIG_SCHEMA_VALIDATION_FAILED = "CONFIG_005"
    
    # System errors (SYSTEM_xx)
    SYSTEM_DATABASE_UNAVAILABLE = "SYSTEM_001"
    SYSTEM_MESSAGE_BUS_UNAVAILABLE = "SYSTEM_002"
    SYSTEM_EXTERNAL_SERVICE_TIMEOUT = "SYSTEM_003"
    SYSTEM_MEMORY_EXHAUSTED = "SYSTEM_004"
    SYSTEM_DISK_FULL = "SYSTEM_005"


class AMRErrorDetail(BaseModel):
    """
    Structured error detail following FHIR OperationOutcome pattern.
    
    Provides actionable information for error triage and resolution.
    """
    code: AMRErrorCode
    severity: ErrorSeverity
    message: str
    details: Optional[str] = None
    path: Optional[str] = None
    location: Optional[str] = None  # File/line for system errors
    context: Dict[str, Any] = {}
    
    @property
    def category(self) -> ErrorCategory:
        """Extract error category from code."""
        return ErrorCategory(self.code.value.split("_")[0])
    
    def to_fhir_issue(self) -> Dict[str, Any]:
        """Convert to FHIR OperationOutcome.issue format."""
        issue = {
            "severity": self.severity.value,
            "code": "invalid" if self.severity in [ErrorSeverity.ERROR, ErrorSeverity.CRITICAL] else "informational",
            "diagnostics": f"[{self.code.value}] {self.message}"
        }
        
        if self.details:
            issue["diagnostics"] += f" - {self.details}"
            
        if self.path:
            issue["expression"] = [self.path]
            
        if self.context:
            issue["diagnostics"] += f" Context: {self.context}"
            
        return issue
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging and API responses."""
        result = {
            "error_code": self.code.value,
            "category": self.category.value, 
            "severity": self.severity.value,
            "message": self.message
        }
        
        if self.details:
            result["details"] = self.details
        if self.path:
            result["path"] = self.path
        if self.location:
            result["location"] = self.location
        if self.context:
            result["context"] = self.context
            
        return result


class AMRException(Exception):
    """
    Base exception class with structured error information.
    
    All AMR-specific exceptions should inherit from this to ensure
    consistent error handling and reporting.
    """
    
    def __init__(
        self,
        error_detail: AMRErrorDetail,
        cause: Optional[Exception] = None
    ):
        self.error_detail = error_detail
        self.cause = cause
        super().__init__(error_detail.message)
    
    @property
    def code(self) -> AMRErrorCode:
        return self.error_detail.code
    
    @property
    def category(self) -> ErrorCategory:
        return self.error_detail.category
    
    @property
    def severity(self) -> ErrorSeverity:
        return self.error_detail.severity
    
    def to_operation_outcome(self) -> Dict[str, Any]:
        """Convert to FHIR OperationOutcome resource."""
        return {
            "resourceType": "OperationOutcome",
            "issue": [self.error_detail.to_fhir_issue()]
        }


class IngestionError(AMRException):
    """Errors during data ingestion (HL7v2, FHIR parsing)."""
    pass


class ClassificationError(AMRException):
    """Errors during AMR classification process.""" 
    pass


class TerminologyError(AMRException):
    """Errors in terminology mapping and resolution."""
    pass


class ProfilePackError(AMRException):
    """Errors in FHIR profile pack operations."""
    pass


class ValidationError(AMRException):
    """Errors during FHIR validation."""
    pass


class AuthenticationError(AMRException):
    """Authentication and authorization errors."""
    pass


class ConfigurationError(AMRException):
    """Configuration and setup errors."""
    pass


class SystemError(AMRException):
    """System-level errors (database, external services)."""
    pass


# Convenience functions for creating common errors

def create_ingestion_error(
    code: AMRErrorCode,
    message: str,
    path: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None
) -> IngestionError:
    """Create a structured ingestion error."""
    return IngestionError(AMRErrorDetail(
        code=code,
        severity=ErrorSeverity.ERROR,
        message=message,
        path=path,
        context=context or {}
    ))


def create_classification_error(
    code: AMRErrorCode,
    message: str,
    details: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None
) -> ClassificationError:
    """Create a structured classification error."""
    return ClassificationError(AMRErrorDetail(
        code=code,
        severity=ErrorSeverity.ERROR,
        message=message,
        details=details,
        context=context or {}
    ))


def create_terminology_error(
    code: AMRErrorCode,
    message: str,
    unmapped_term: Optional[str] = None,
    code_system: Optional[str] = None
) -> TerminologyError:
    """Create a structured terminology error."""
    context = {}
    if unmapped_term:
        context["unmapped_term"] = unmapped_term
    if code_system:
        context["code_system"] = code_system
        
    return TerminologyError(AMRErrorDetail(
        code=code,
        severity=ErrorSeverity.WARNING,
        message=message,
        context=context
    ))


def create_validation_error(
    code: AMRErrorCode, 
    message: str,
    path: Optional[str] = None,
    binding_strength: Optional[str] = None,
    profile_pack: Optional[str] = None
) -> ValidationError:
    """Create a structured validation error."""
    context = {}
    if binding_strength:
        context["binding_strength"] = binding_strength  
    if profile_pack:
        context["profile_pack"] = profile_pack
        
    return ValidationError(AMRErrorDetail(
        code=code,
        severity=ErrorSeverity.ERROR,
        message=message,
        path=path,
        context=context
    ))


def create_auth_error(
    code: AMRErrorCode,
    message: str,
    user_id: Optional[str] = None,
    required_scope: Optional[str] = None
) -> AuthenticationError:
    """Create a structured authentication error."""
    context = {}
    if user_id:
        context["user_id"] = user_id
    if required_scope:
        context["required_scope"] = required_scope
        
    return AuthenticationError(AMRErrorDetail(
        code=code,
        severity=ErrorSeverity.ERROR,
        message=message, 
        context=context
    ))


# Error code mapping for quick lookup
ERROR_MESSAGES = {
    AMRErrorCode.INGEST_INVALID_HL7: "Invalid HL7v2 message format",
    AMRErrorCode.INGEST_MISSING_SEGMENT: "Required HL7v2 segment missing",
    AMRErrorCode.INGEST_INVALID_FHIR: "Invalid FHIR resource structure",
    AMRErrorCode.CLASSIFY_NO_RULES_FOUND: "No applicable classification rules found",
    AMRErrorCode.CLASSIFY_MISSING_ORGANISM: "Organism identification required for classification",
    AMRErrorCode.TERM_UNMAPPED_ORGANISM: "Organism not found in terminology mappings",
    AMRErrorCode.PACK_NOT_FOUND: "Requested profile pack not available",
    AMRErrorCode.VALID_STRUCTURE_DEFINITION_FAILED: "FHIR resource failed StructureDefinition validation",
    AMRErrorCode.AUTH_INSUFFICIENT_SCOPE: "Insufficient OAuth2 scope for requested operation",
    AMRErrorCode.CONFIG_RULES_LOAD_FAILED: "Failed to load AMR classification rules"
}


def get_error_message(code: AMRErrorCode) -> str:
    """Get standard error message for error code."""
    return ERROR_MESSAGES.get(code, f"Unknown error: {code.value}")