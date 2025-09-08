"""
AMR Engine Policy Management and Validation.

Implements policy.json schema validation and policy enforcement
for access control, validation rules, and operational settings.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import jsonschema
from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)


class PolicyMetadata(BaseModel):
    """Policy metadata information."""
    name: str
    description: str
    author: str
    created: Optional[str] = None
    lastModified: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class AuthenticationConfig(BaseModel):
    """Authentication configuration."""
    required: bool = True
    methods: List[str] = Field(default_factory=lambda: ["static-token"])
    staticToken: Optional[Dict[str, bool]] = None
    oauth2: Optional[Dict[str, Any]] = None
    mtls: Optional[Dict[str, Any]] = None


class RoleConfig(BaseModel):
    """RBAC role configuration."""
    description: str
    permissions: List[str]
    tenants: List[str] = Field(default_factory=list)


class AuthorizationConfig(BaseModel):
    """Authorization configuration."""
    rbac: Optional[Dict[str, Any]] = None


class AccessControlConfig(BaseModel):
    """Access control policies."""
    authentication: Optional[AuthenticationConfig] = None
    authorization: Optional[AuthorizationConfig] = None


class FHIRValidationConfig(BaseModel):
    """FHIR validation configuration."""
    strictValidation: bool = False
    allowedProfiles: List[str] = Field(default_factory=lambda: ["Base"])
    defaultProfile: str = "Base"
    validateReferences: bool = False


class ClassificationValidationConfig(BaseModel):
    """Classification validation configuration."""
    requireSpecimen: bool = False
    allowMissingValues: bool = True
    validationLevel: str = "standard"
    maxBatchSize: int = 100


class ValidationConfig(BaseModel):
    """Validation policies."""
    fhir: Optional[FHIRValidationConfig] = None
    classification: Optional[ClassificationValidationConfig] = None


class RateLimitConfig(BaseModel):
    """Rate limiting configuration."""
    enabled: bool = False
    requestsPerMinute: int = 60
    burstSize: int = 10
    perTenant: bool = False


class CachingConfig(BaseModel):
    """Caching configuration."""
    enabled: bool = True
    ruleCacheTtl: int = 3600
    terminologyCacheTtl: int = 7200


class AuditConfig(BaseModel):
    """Audit configuration."""
    enabled: bool = True
    auditAllClassifications: bool = False
    auditFailuresOnly: bool = False
    retentionDays: int = 365


class OperationalConfig(BaseModel):
    """Operational policies."""
    rateLimit: Optional[RateLimitConfig] = None
    caching: Optional[CachingConfig] = None
    audit: Optional[AuditConfig] = None


class SecurityConfig(BaseModel):
    """Security policies."""
    encryption: Optional[Dict[str, Any]] = None
    cors: Optional[Dict[str, Any]] = None
    headers: Optional[Dict[str, Any]] = None


class AMRPolicy(BaseModel):
    """Complete AMR Engine policy configuration."""
    version: str
    metadata: PolicyMetadata
    accessControl: Optional[AccessControlConfig] = None
    validation: Optional[ValidationConfig] = None
    operational: Optional[OperationalConfig] = None
    security: Optional[SecurityConfig] = None


class PolicyValidator:
    """Policy file validator using JSON Schema."""
    
    def __init__(self, schema_path: Optional[Path] = None):
        if schema_path is None:
            # Default to schema in the schemas directory
            current_dir = Path(__file__).parent.parent
            schema_path = current_dir / "schemas" / "policy-schema.json"
        
        self.schema_path = schema_path
        self._schema: Optional[Dict[str, Any]] = None
        self._load_schema()
    
    def _load_schema(self):
        """Load the JSON schema from file."""
        try:
            if not self.schema_path.exists():
                raise FileNotFoundError(f"Policy schema not found at {self.schema_path}")
            
            with open(self.schema_path, 'r', encoding='utf-8') as f:
                self._schema = json.load(f)
                
            logger.info(f"Loaded policy schema from {self.schema_path}")
            
        except Exception as e:
            logger.error(f"Failed to load policy schema: {e}")
            raise
    
    def validate_policy_file(self, policy_path: Path) -> bool:
        """Validate a policy.json file against the schema."""
        try:
            if not policy_path.exists():
                raise FileNotFoundError(f"Policy file not found: {policy_path}")
            
            with open(policy_path, 'r', encoding='utf-8') as f:
                policy_data = json.load(f)
            
            return self.validate_policy_data(policy_data, str(policy_path))
            
        except Exception as e:
            logger.error(f"Failed to validate policy file {policy_path}: {e}")
            return False
    
    def validate_policy_data(self, policy_data: Dict[str, Any], source: str = "data") -> bool:
        """Validate policy data against the schema."""
        if not self._schema:
            raise RuntimeError("Policy schema not loaded")
        
        try:
            # Validate against JSON schema
            jsonschema.validate(policy_data, self._schema)
            logger.info(f"Policy {source} passed JSON schema validation")
            
            # Validate against Pydantic model for additional validation
            AMRPolicy(**policy_data)
            logger.info(f"Policy {source} passed Pydantic model validation")
            
            return True
            
        except jsonschema.ValidationError as e:
            logger.error(f"Policy {source} failed JSON schema validation: {e.message}")
            logger.error(f"Failed at path: {' -> '.join(str(x) for x in e.absolute_path)}")
            return False
            
        except ValidationError as e:
            logger.error(f"Policy {source} failed Pydantic validation: {e}")
            return False
        
        except Exception as e:
            logger.error(f"Unexpected error validating policy {source}: {e}")
            return False
    
    def get_validation_errors(self, policy_data: Dict[str, Any]) -> List[str]:
        """Get detailed validation errors for policy data."""
        errors = []
        
        if not self._schema:
            return ["Policy schema not loaded"]
        
        try:
            # Check JSON schema validation
            jsonschema.validate(policy_data, self._schema)
        except jsonschema.ValidationError as e:
            errors.append(f"Schema validation: {e.message} at {' -> '.join(str(x) for x in e.absolute_path)}")
        except Exception as e:
            errors.append(f"Schema validation error: {str(e)}")
        
        try:
            # Check Pydantic model validation
            AMRPolicy(**policy_data)
        except ValidationError as e:
            for error in e.errors():
                loc = ' -> '.join(str(x) for x in error['loc'])
                errors.append(f"Model validation: {error['msg']} at {loc}")
        except Exception as e:
            errors.append(f"Model validation error: {str(e)}")
        
        return errors


class PolicyManager:
    """Manages policy loading, validation, and enforcement."""
    
    def __init__(self, policy_paths: Optional[List[Path]] = None):
        self.policy_paths = policy_paths or []
        self.policies: Dict[str, AMRPolicy] = {}
        self.validator = PolicyValidator()
        self._load_policies()
    
    def _load_policies(self):
        """Load and validate all policy files."""
        for policy_path in self.policy_paths:
            try:
                if self.validator.validate_policy_file(policy_path):
                    with open(policy_path, 'r', encoding='utf-8') as f:
                        policy_data = json.load(f)
                    
                    policy = AMRPolicy(**policy_data)
                    self.policies[policy.metadata.name] = policy
                    logger.info(f"Loaded policy: {policy.metadata.name}")
                else:
                    logger.error(f"Failed to validate policy file: {policy_path}")
            
            except Exception as e:
                logger.error(f"Error loading policy from {policy_path}: {e}")
    
    def add_policy_path(self, policy_path: Path):
        """Add a new policy file path and load it."""
        if policy_path not in self.policy_paths:
            self.policy_paths.append(policy_path)
            
            if self.validator.validate_policy_file(policy_path):
                try:
                    with open(policy_path, 'r', encoding='utf-8') as f:
                        policy_data = json.load(f)
                    
                    policy = AMRPolicy(**policy_data)
                    self.policies[policy.metadata.name] = policy
                    logger.info(f"Added and loaded policy: {policy.metadata.name}")
                    
                except Exception as e:
                    logger.error(f"Error loading new policy from {policy_path}: {e}")
    
    def get_policy(self, name: str) -> Optional[AMRPolicy]:
        """Get a policy by name."""
        return self.policies.get(name)
    
    def list_policies(self) -> List[str]:
        """List all loaded policy names."""
        return list(self.policies.keys())
    
    def validate_all_policies(self) -> Dict[str, bool]:
        """Validate all loaded policies and return results."""
        results = {}
        
        for policy_path in self.policy_paths:
            policy_name = policy_path.stem
            results[policy_name] = self.validator.validate_policy_file(policy_path)
        
        return results
    
    def get_effective_policy(self, policy_names: Optional[List[str]] = None) -> Optional[AMRPolicy]:
        """
        Get effective policy by merging multiple policies.
        Later policies override earlier ones.
        """
        if not policy_names:
            policy_names = list(self.policies.keys())
        
        if not policy_names:
            return None
        
        # Start with first policy
        effective_data = self.policies[policy_names[0]].model_dump()
        
        # Merge subsequent policies
        for name in policy_names[1:]:
            if name in self.policies:
                policy_data = self.policies[name].model_dump()
                effective_data = self._merge_policies(effective_data, policy_data)
        
        return AMRPolicy(**effective_data)
    
    def _merge_policies(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Merge two policy dictionaries, with override taking precedence."""
        merged = base.copy()
        
        for key, value in override.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key] = self._merge_policies(merged[key], value)
            else:
                merged[key] = value
        
        return merged


# Global policy manager instance
policy_manager = PolicyManager()