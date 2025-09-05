"""
FHIR Profile Pack Validation Framework for AMR Classification Engine.

Implements multi-profile pack validation as recommended in the AMR Unified System
architecture document. Supports IL-Core, US-Core, IPS, and custom profile packs
with versioning, conflict resolution, and tenant-specific overrides.
"""

from __future__ import annotations

import json
import logging
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, Field, validator
from typing_extensions import Literal

from .audit import AMRAuditLogger, AuditEventOutcome
from .errors import (
    AMRErrorCode,
    ProfilePackError,
    ValidationError,
    create_validation_error
)
from .metrics import metrics
from .tracing import get_tracer

logger = logging.getLogger(__name__)


class ProfilePackType(str, Enum):
    """Supported FHIR profile pack types."""
    IL_CORE = "il-core"
    US_CORE = "us-core" 
    IPS = "ips"
    CUSTOM = "custom"


class ValidationSeverity(str, Enum):
    """FHIR validation severity levels."""
    ERROR = "error"
    WARNING = "warning"
    INFORMATION = "information"


class BindingStrength(str, Enum):
    """FHIR value set binding strengths."""
    REQUIRED = "required"
    EXTENSIBLE = "extensible"
    PREFERRED = "preferred"
    EXAMPLE = "example"


class ProfilePackManifest(BaseModel):
    """
    Profile pack manifest defining validation rules and metadata.
    
    Contains information about supported profiles, value sets,
    versioning, and tenant-specific configurations.
    """
    pack_id: str = Field(..., description="Unique profile pack identifier")
    pack_type: ProfilePackType = Field(..., description="Profile pack type")
    version: str = Field(..., description="Semantic version (e.g., 1.0.0)")
    display_name: str = Field(..., description="Human-readable pack name")
    description: Optional[str] = None
    
    # FHIR version compatibility
    fhir_version: str = Field(default="4.0.1", description="Supported FHIR version")
    
    # Supported resource profiles
    supported_profiles: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Resource type to profile URL mapping with validation rules"
    )
    
    # Value set bindings
    value_sets: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Value set definitions and binding configurations"
    )
    
    # Validation rules
    validation_rules: Dict[str, Any] = Field(
        default_factory=dict,
        description="Custom validation rules and constraints"
    )
    
    # Tenant-specific overrides
    tenant_overrides: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Tenant-specific validation overrides"
    )
    
    # Conflict resolution priorities
    conflict_resolution: Dict[str, int] = Field(
        default_factory=dict,
        description="Priority scores for conflict resolution (higher = preferred)"
    )
    
    @validator("version")
    def validate_semantic_version(cls, v):
        """Validate semantic versioning format."""
        parts = v.split(".")
        if len(parts) != 3 or not all(part.isdigit() for part in parts):
            raise ValueError("Version must follow semantic versioning (x.y.z)")
        return v


class ValidationIssue(BaseModel):
    """Individual validation issue with context."""
    severity: ValidationSeverity
    code: str
    path: Optional[str] = None
    message: str
    profile_pack: str
    binding_type: Optional[str] = None
    binding_strength: Optional[BindingStrength] = None
    context: Dict[str, Any] = Field(default_factory=dict)


class ValidationResult(BaseModel):
    """Comprehensive validation result."""
    valid: bool
    profile_pack: str
    pack_version: str
    resource_type: str
    issues: List[ValidationIssue] = Field(default_factory=list)
    applied_profiles: List[str] = Field(default_factory=list)
    binding_failures: Dict[str, int] = Field(default_factory=dict)
    tenant_id: Optional[str] = None


class ProfilePackRegistry:
    """
    Registry for managing multiple FHIR profile packs.
    
    Handles pack loading, versioning, tenant assignment,
    and conflict resolution between overlapping profiles.
    """
    
    def __init__(self, base_path: Optional[Path] = None):
        self.base_path = base_path or Path("profile_packs")
        self.packs: Dict[str, Dict[str, ProfilePackManifest]] = {}  # pack_id -> version -> manifest
        self.tenant_assignments: Dict[str, str] = {}  # tenant_id -> pack_id
        self.default_pack: Optional[str] = None
        
        # Initialize with built-in packs
        self._load_builtin_packs()
    
    def _load_builtin_packs(self):
        """Load built-in profile packs (IL-Core, US-Core, IPS)."""
        builtin_packs = [
            {
                "pack_id": "il-core-1.0.0",
                "pack_type": ProfilePackType.IL_CORE,
                "version": "1.0.0",
                "display_name": "IL Core Implementation Guide",
                "description": "Israeli national FHIR implementation guide",
                "supported_profiles": {
                    "Observation": {
                        "profile_url": "http://fhir.health.gov.il/StructureDefinition/il-core-observation",
                        "required_elements": ["status", "code", "subject"],
                        "value_set_bindings": {
                            "status": {
                                "strength": "required",
                                "value_set": "http://hl7.org/fhir/ValueSet/observation-status"
                            }
                        }
                    },
                    "Patient": {
                        "profile_url": "http://fhir.health.gov.il/StructureDefinition/il-core-patient",
                        "required_elements": ["identifier"]
                    }
                },
                "conflict_resolution": {"default": 80}
            },
            {
                "pack_id": "us-core-5.0.1",
                "pack_type": ProfilePackType.US_CORE,
                "version": "5.0.1", 
                "display_name": "US Core Implementation Guide v5.0.1",
                "description": "US national FHIR implementation guide",
                "supported_profiles": {
                    "Observation": {
                        "profile_url": "http://hl7.org/fhir/us/core/StructureDefinition/us-core-observation-lab",
                        "required_elements": ["status", "category", "code", "subject"],
                        "value_set_bindings": {
                            "status": {
                                "strength": "required",
                                "value_set": "http://hl7.org/fhir/ValueSet/observation-status"
                            },
                            "category": {
                                "strength": "extensible",
                                "value_set": "http://terminology.hl7.org/ValueSet/observation-category"
                            }
                        }
                    }
                },
                "conflict_resolution": {"default": 90}
            },
            {
                "pack_id": "ips-1.1.0",
                "pack_type": ProfilePackType.IPS,
                "version": "1.1.0",
                "display_name": "International Patient Summary v1.1.0",
                "description": "HL7 International Patient Summary implementation guide",
                "supported_profiles": {
                    "Observation": {
                        "profile_url": "http://hl7.org/fhir/uv/ips/StructureDefinition/Observation-results-uv-ips",
                        "required_elements": ["status", "code", "subject"]
                    }
                },
                "conflict_resolution": {"default": 70}
            }
        ]
        
        for pack_data in builtin_packs:
            manifest = ProfilePackManifest(**pack_data)
            self.register_pack(manifest)
    
    def register_pack(self, manifest: ProfilePackManifest):
        """Register a new profile pack."""
        pack_id = manifest.pack_id
        version = manifest.version
        
        if pack_id not in self.packs:
            self.packs[pack_id] = {}
        
        self.packs[pack_id][version] = manifest
        logger.info(f"Registered profile pack: {pack_id} v{version}")
    
    def assign_tenant_pack(self, tenant_id: str, pack_id: str):
        """Assign a specific profile pack to a tenant."""
        if pack_id not in self.packs:
            raise ProfilePackError(f"Profile pack '{pack_id}' not found")
        
        self.tenant_assignments[tenant_id] = pack_id
        logger.info(f"Assigned pack '{pack_id}' to tenant '{tenant_id}'")
    
    def get_pack_for_tenant(self, tenant_id: Optional[str] = None) -> Optional[ProfilePackManifest]:
        """Get the appropriate profile pack for a tenant."""
        if tenant_id and tenant_id in self.tenant_assignments:
            pack_id = self.tenant_assignments[tenant_id]
            # Get latest version
            if pack_id in self.packs:
                latest_version = max(self.packs[pack_id].keys())
                return self.packs[pack_id][latest_version]
        
        # Fall back to default pack
        if self.default_pack and self.default_pack in self.packs:
            latest_version = max(self.packs[self.default_pack].keys())
            return self.packs[self.default_pack][latest_version]
        
        # Fall back to highest priority pack
        best_pack = None
        best_priority = -1
        
        for pack_id, versions in self.packs.items():
            latest_version = max(versions.keys())
            manifest = versions[latest_version]
            priority = manifest.conflict_resolution.get("default", 0)
            if priority > best_priority:
                best_priority = priority
                best_pack = manifest
        
        return best_pack
    
    def list_available_packs(self) -> List[Dict[str, Any]]:
        """List all available profile packs with metadata."""
        packs = []
        for pack_id, versions in self.packs.items():
            latest_version = max(versions.keys())
            manifest = versions[latest_version]
            packs.append({
                "pack_id": pack_id,
                "pack_type": manifest.pack_type.value,
                "version": latest_version,
                "display_name": manifest.display_name,
                "description": manifest.description,
                "supported_resources": list(manifest.supported_profiles.keys())
            })
        return packs


class ProfilePackValidator:
    """
    FHIR resource validator using profile pack definitions.
    
    Validates FHIR resources against selected profile packs with
    comprehensive error reporting and audit trail generation.
    """
    
    def __init__(
        self,
        registry: ProfilePackRegistry,
        audit_logger: Optional[AMRAuditLogger] = None
    ):
        self.registry = registry
        self.audit_logger = audit_logger or AMRAuditLogger()
        self.tracer = get_tracer()
    
    @get_tracer().trace_fhir_operation(resource_type="Resource", operation="validate")
    async def validate_resource(
        self,
        resource: Dict[str, Any],
        tenant_id: Optional[str] = None,
        profile_override: Optional[str] = None
    ) -> ValidationResult:
        """
        Validate a FHIR resource against the appropriate profile pack.
        
        Args:
            resource: FHIR resource to validate
            tenant_id: Optional tenant identifier for pack selection
            profile_override: Optional specific profile pack to use
            
        Returns:
            Comprehensive validation result with issues and metadata
        """
        resource_type = resource.get("resourceType")
        if not resource_type:
            raise ValidationError("Resource must have resourceType")
        
        # Select profile pack
        if profile_override:
            pack = self._get_pack_by_id(profile_override)
        else:
            pack = self.registry.get_pack_for_tenant(tenant_id)
        
        if not pack:
            raise ProfilePackError("No suitable profile pack found")
        
        # Record pack selection in audit log
        audit_event = self.audit_logger.create_profile_selection_event(
            profile_pack=pack.pack_id,
            pack_version=pack.version,
            tenant_id=tenant_id,
            override_source="explicit" if profile_override else "tenant_assignment"
        )
        
        # Record metrics
        metrics.record_profile_selection(
            profile_pack=pack.pack_id,
            selection_source="override" if profile_override else "tenant",
            tenant_id=tenant_id
        )
        
        with self.tracer.trace_profile_validation(pack.pack_id, resource_type) as span:
            span.set_attribute("pack_version", pack.version)
            span.set_attribute("tenant_id", tenant_id or "default")
            
            # Perform validation
            result = await self._validate_against_pack(resource, pack, tenant_id)
            
            # Add trace attributes
            span.set_attribute("validation_success", result.valid)
            span.set_attribute("issue_count", len(result.issues))
            
            # Record metrics
            metrics.record_profile_validation(
                profile_pack=pack.pack_id,
                pack_version=pack.version,
                success=result.valid,
                binding_failures=result.binding_failures
            )
            
            return result
    
    async def _validate_against_pack(
        self,
        resource: Dict[str, Any],
        pack: ProfilePackManifest,
        tenant_id: Optional[str]
    ) -> ValidationResult:
        """Validate resource against specific profile pack."""
        resource_type = resource["resourceType"]
        issues: List[ValidationIssue] = []
        applied_profiles: List[str] = []
        binding_failures: Dict[str, int] = {}
        
        # Check if resource type is supported
        if resource_type not in pack.supported_profiles:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                code="unsupported-resource-type",
                message=f"Resource type '{resource_type}' not supported by profile pack '{pack.pack_id}'",
                profile_pack=pack.pack_id
            ))
            return ValidationResult(
                valid=len([i for i in issues if i.severity == ValidationSeverity.ERROR]) == 0,
                profile_pack=pack.pack_id,
                pack_version=pack.version,
                resource_type=resource_type,
                issues=issues,
                applied_profiles=applied_profiles,
                binding_failures=binding_failures,
                tenant_id=tenant_id
            )
        
        profile_def = pack.supported_profiles[resource_type]
        profile_url = profile_def.get("profile_url")
        if profile_url:
            applied_profiles.append(profile_url)
        
        # Apply tenant-specific overrides
        if tenant_id and tenant_id in pack.tenant_overrides:
            tenant_rules = pack.tenant_overrides[tenant_id]
            if resource_type in tenant_rules:
                profile_def = {**profile_def, **tenant_rules[resource_type]}
        
        # Validate required elements
        required_elements = profile_def.get("required_elements", [])
        for element in required_elements:
            if not self._element_exists(resource, element):
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    code="required-element-missing",
                    path=element,
                    message=f"Required element '{element}' is missing",
                    profile_pack=pack.pack_id
                ))
        
        # Validate value set bindings
        bindings = profile_def.get("value_set_bindings", {})
        for element_path, binding_def in bindings.items():
            binding_strength = BindingStrength(binding_def.get("strength", "example"))
            value_set_url = binding_def.get("value_set")
            
            if self._element_exists(resource, element_path):
                element_value = self._get_element_value(resource, element_path)
                is_valid = await self._validate_value_set_binding(
                    element_value, value_set_url, binding_strength
                )
                
                if not is_valid:
                    binding_key = f"{element_path}:{binding_strength.value}"
                    binding_failures[binding_key] = binding_failures.get(binding_key, 0) + 1
                    
                    severity = (ValidationSeverity.ERROR if binding_strength == BindingStrength.REQUIRED
                              else ValidationSeverity.WARNING)
                    
                    issues.append(ValidationIssue(
                        severity=severity,
                        code="valueset-binding-failed",
                        path=element_path,
                        message=f"Value does not conform to {binding_strength.value} binding for value set '{value_set_url}'",
                        profile_pack=pack.pack_id,
                        binding_type=element_path,
                        binding_strength=binding_strength,
                        context={"value": element_value, "value_set": value_set_url}
                    ))
        
        # Apply custom validation rules
        custom_issues = await self._apply_custom_validation_rules(
            resource, pack.validation_rules, pack.pack_id
        )
        issues.extend(custom_issues)
        
        return ValidationResult(
            valid=len([i for i in issues if i.severity == ValidationSeverity.ERROR]) == 0,
            profile_pack=pack.pack_id,
            pack_version=pack.version,
            resource_type=resource_type,
            issues=issues,
            applied_profiles=applied_profiles,
            binding_failures=binding_failures,
            tenant_id=tenant_id
        )
    
    def _get_pack_by_id(self, pack_id: str) -> Optional[ProfilePackManifest]:
        """Get profile pack by ID (latest version)."""
        if pack_id in self.registry.packs:
            latest_version = max(self.registry.packs[pack_id].keys())
            return self.registry.packs[pack_id][latest_version]
        return None
    
    def _element_exists(self, resource: Dict[str, Any], path: str) -> bool:
        """Check if an element exists in the resource using dot notation."""
        parts = path.split(".")
        current = resource
        
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return False
        return True
    
    def _get_element_value(self, resource: Dict[str, Any], path: str) -> Any:
        """Get element value using dot notation."""
        parts = path.split(".")
        current = resource
        
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return current
    
    async def _validate_value_set_binding(
        self,
        value: Any,
        value_set_url: str,
        strength: BindingStrength
    ) -> bool:
        """Validate value against value set binding."""
        # Simplified validation - in production this would use a terminology service
        if strength == BindingStrength.EXAMPLE:
            return True  # Example bindings are always valid
        
        # For now, accept common FHIR codes
        if isinstance(value, str) and value in ["final", "preliminary", "active", "inactive"]:
            return True
        
        # For CodeableConcept, check coding array
        if isinstance(value, dict) and "coding" in value:
            codings = value["coding"]
            if isinstance(codings, list) and codings:
                # Accept any coding for now
                return True
        
        # For required bindings, be strict
        return strength != BindingStrength.REQUIRED
    
    async def _apply_custom_validation_rules(
        self,
        resource: Dict[str, Any],
        rules: Dict[str, Any],
        pack_id: str
    ) -> List[ValidationIssue]:
        """Apply custom validation rules defined in the profile pack."""
        issues: List[ValidationIssue] = []
        
        # Placeholder for custom rule engine
        # In production, this would implement a flexible rule evaluation system
        
        return issues


# Global registry instance
profile_registry = ProfilePackRegistry()
profile_validator = ProfilePackValidator(profile_registry)