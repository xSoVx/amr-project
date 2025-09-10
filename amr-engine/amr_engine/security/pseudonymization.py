"""
Patient Identifier Pseudonymization Service

This module provides cryptographic pseudonymization of patient identifiers
to protect PHI while maintaining data utility for AMR analysis. Uses HMAC-SHA256
with configurable salt for consistent, reversible pseudonymization.

Security Features:
- Cryptographic hashing with HMAC-SHA256
- Configurable salt for enhanced security
- Bidirectional mapping storage with AES encryption
- Multiple identifier type support (Patient ID, MRN, SSN, etc.)
- Consistent dummy ID generation across requests
"""

import os
import hmac
import hashlib
import secrets
import base64
import logging
from typing import Dict, List, Optional, Set, Union, Any
from dataclasses import dataclass, field
from pathlib import Path
import json
import re
from datetime import datetime, timezone
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)


@dataclass
class IdentifierMapping:
    """Represents a pseudonymized identifier mapping"""
    original_id: str
    pseudonymized_id: str
    identifier_type: str
    created_at: str
    last_accessed: str
    access_count: int = 0


@dataclass
class PseudonymizationConfig:
    """Configuration for pseudonymization service"""
    salt_key: str = field(default_factory=lambda: os.getenv('PSEUDONYM_SALT_KEY', secrets.token_hex(32)))
    encryption_key: Optional[str] = field(default_factory=lambda: os.getenv('PSEUDONYM_ENCRYPTION_KEY'))
    storage_path: Path = field(default_factory=lambda: Path("./pseudonym_storage"))
    dummy_id_prefix: str = "PSY"
    dummy_id_length: int = 12
    supported_id_types: Set[str] = field(default_factory=lambda: {
        "Patient", "patient_id", "patientId", "patient_identifier",
        "MRN", "mrn", "medical_record_number",
        "SSN", "ssn", "social_security_number",
        "specimen_id", "specimenId", "specimen_identifier",
        "subject", "reference"
    })


class PseudonymizationService:
    """
    Cryptographic patient identifier pseudonymization service.
    
    Provides secure, consistent pseudonymization of patient identifiers
    across all message formats (FHIR R4, HL7v2, JSON) while maintaining
    bidirectional mapping for audit and debugging purposes.
    """
    
    def __init__(self, config: Optional[PseudonymizationConfig] = None):
        """
        Initialize pseudonymization service.
        
        Args:
            config: Pseudonymization configuration. Uses defaults if not provided.
        """
        self.config = config or PseudonymizationConfig()
        self._mapping_cache: Dict[str, IdentifierMapping] = {}
        self._reverse_mapping: Dict[str, str] = {}
        self._cipher_suite: Optional[Fernet] = None
        
        # Initialize encryption if key is provided
        if self.config.encryption_key:
            self._initialize_encryption()
        
        # Ensure storage directory exists
        self.config.storage_path.mkdir(parents=True, exist_ok=True)
        
        # Load existing mappings
        self._load_mappings()
        
        logger.info(f"PseudonymizationService initialized with {len(self._mapping_cache)} existing mappings")
    
    def _initialize_encryption(self):
        """Initialize Fernet encryption for mapping storage."""
        try:
            if len(self.config.encryption_key) == 44:  # Base64 encoded Fernet key
                key = self.config.encryption_key.encode()
            else:
                # Generate key from password using PBKDF2
                kdf = PBKDF2HMAC(
                    algorithm=hashes.SHA256(),
                    length=32,
                    salt=self.config.salt_key.encode()[:16],
                    iterations=100000,
                )
                key = base64.urlsafe_b64encode(kdf.derive(self.config.encryption_key.encode()))
            
            self._cipher_suite = Fernet(key)
            logger.info("Encryption initialized for pseudonymization mappings")
        except Exception as e:
            logger.error(f"Failed to initialize encryption: {e}")
            self._cipher_suite = None
    
    def _generate_pseudonym(self, original_id: str, identifier_type: str) -> str:
        """
        Generate cryptographically secure pseudonym for identifier.
        
        Args:
            original_id: Original patient identifier
            identifier_type: Type of identifier (Patient, MRN, SSN, etc.)
        
        Returns:
            Consistent pseudonymized identifier
        """
        # Create HMAC with salt and identifier type for additional entropy
        message = f"{identifier_type}:{original_id}".encode('utf-8')
        salt = self.config.salt_key.encode('utf-8')
        
        # Generate HMAC-SHA256 hash
        signature = hmac.new(salt, message, hashlib.sha256).hexdigest()
        
        # Create readable dummy ID
        # Use first 8 chars of hash for uniqueness, add type prefix
        hash_part = signature[:8].upper()
        type_prefix = self._get_type_prefix(identifier_type)
        
        pseudonym = f"{self.config.dummy_id_prefix}-{type_prefix}-{hash_part}"
        
        return pseudonym
    
    def _get_type_prefix(self, identifier_type: str) -> str:
        """Get 2-character prefix for identifier type."""
        type_mapping = {
            "Patient": "PT", "patient_id": "PT", "patientId": "PT",
            "MRN": "MR", "mrn": "MR", "medical_record_number": "MR",
            "SSN": "SS", "ssn": "SS", "social_security_number": "SS",
            "specimen_id": "SP", "specimenId": "SP", "specimen_identifier": "SP",
            "subject": "SU", "reference": "RF"
        }
        return type_mapping.get(identifier_type, "ID")
    
    def pseudonymize_identifier(
        self, 
        original_id: str, 
        identifier_type: str = "Patient"
    ) -> str:
        """
        Pseudonymize a single identifier.
        
        Args:
            original_id: Original identifier to pseudonymize
            identifier_type: Type of identifier
        
        Returns:
            Pseudonymized identifier
        """
        if not original_id or not original_id.strip():
            return original_id
        
        # Check cache first
        cache_key = f"{identifier_type}:{original_id}"
        if cache_key in self._mapping_cache:
            mapping = self._mapping_cache[cache_key]
            mapping.access_count += 1
            mapping.last_accessed = datetime.now(timezone.utc).isoformat()
            return mapping.pseudonymized_id
        
        # Generate new pseudonym
        pseudonymized_id = self._generate_pseudonym(original_id, identifier_type)
        
        # Create mapping
        mapping = IdentifierMapping(
            original_id=original_id,
            pseudonymized_id=pseudonymized_id,
            identifier_type=identifier_type,
            created_at=datetime.now(timezone.utc).isoformat(),
            last_accessed=datetime.now(timezone.utc).isoformat(),
            access_count=1
        )
        
        # Store in cache
        self._mapping_cache[cache_key] = mapping
        self._reverse_mapping[pseudonymized_id] = original_id
        
        # Persist mapping
        self._save_mapping(mapping)
        
        logger.debug(f"Pseudonymized {identifier_type} identifier: {original_id[:4]}*** -> {pseudonymized_id}")
        
        return pseudonymized_id
    
    def depseudonymize_identifier(self, pseudonymized_id: str) -> Optional[str]:
        """
        Reverse pseudonymization to get original identifier.
        
        Args:
            pseudonymized_id: Pseudonymized identifier
        
        Returns:
            Original identifier if found, None otherwise
        """
        return self._reverse_mapping.get(pseudonymized_id)
    
    def pseudonymize_fhir_bundle(self, bundle: Dict[str, Any]) -> Dict[str, Any]:
        """
        Pseudonymize patient identifiers in FHIR Bundle.
        
        Args:
            bundle: FHIR Bundle or single resource
        
        Returns:
            Bundle with pseudonymized identifiers
        """
        if not isinstance(bundle, dict):
            return bundle
        
        # Deep copy to avoid modifying original
        import copy
        pseudonymized_bundle = copy.deepcopy(bundle)
        
        # Process Bundle entries
        if pseudonymized_bundle.get("resourceType") == "Bundle" and "entry" in pseudonymized_bundle:
            for entry in pseudonymized_bundle["entry"]:
                if "resource" in entry:
                    self._pseudonymize_fhir_resource(entry["resource"])
        
        # Process single resource
        elif "resourceType" in pseudonymized_bundle:
            self._pseudonymize_fhir_resource(pseudonymized_bundle)
        
        return pseudonymized_bundle
    
    def _pseudonymize_fhir_resource(self, resource: Dict[str, Any]):
        """Recursively pseudonymize identifiers in FHIR resource."""
        if not isinstance(resource, dict):
            return
        
        # Pseudonymize Patient references
        if "subject" in resource and isinstance(resource["subject"], dict):
            if "reference" in resource["subject"]:
                ref = resource["subject"]["reference"]
                if ref.startswith("Patient/"):
                    patient_id = ref.replace("Patient/", "")
                    pseudonymized_id = self.pseudonymize_identifier(patient_id, "Patient")
                    resource["subject"]["reference"] = f"Patient/{pseudonymized_id}"
        
        # Pseudonymize direct patient identifiers
        if resource.get("resourceType") == "Patient":
            if "id" in resource:
                resource["id"] = self.pseudonymize_identifier(resource["id"], "Patient")
            
            # Pseudonymize patient identifiers array
            if "identifier" in resource:
                for identifier in resource["identifier"]:
                    if isinstance(identifier, dict) and "value" in identifier:
                        # Determine identifier type from system
                        id_type = self._get_identifier_type_from_system(identifier.get("system", ""))
                        identifier["value"] = self.pseudonymize_identifier(identifier["value"], id_type)
        
        # Pseudonymize specimen references
        if "specimen" in resource:
            if isinstance(resource["specimen"], dict) and "reference" in resource["specimen"]:
                ref = resource["specimen"]["reference"]
                if ref.startswith("Specimen/"):
                    specimen_id = ref.replace("Specimen/", "")
                    pseudonymized_id = self.pseudonymize_identifier(specimen_id, "specimen_id")
                    resource["specimen"]["reference"] = f"Specimen/{pseudonymized_id}"
        
        # Recursively process nested objects
        for key, value in resource.items():
            if isinstance(value, dict):
                self._pseudonymize_fhir_resource(value)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        self._pseudonymize_fhir_resource(item)
    
    def _get_identifier_type_from_system(self, system: str) -> str:
        """Determine identifier type from FHIR system URI."""
        if "ssn" in system.lower() or "social" in system.lower():
            return "SSN"
        elif "mrn" in system.lower() or "medical" in system.lower():
            return "MRN"
        elif "patient" in system.lower():
            return "Patient"
        else:
            return "Patient"  # Default
    
    def pseudonymize_hl7v2_message(self, hl7_message: str) -> str:
        """
        Pseudonymize patient identifiers in HL7v2 message.
        
        Args:
            hl7_message: Raw HL7v2 message
        
        Returns:
            HL7v2 message with pseudonymized identifiers
        """
        if not hl7_message:
            return hl7_message
        
        lines = hl7_message.split('\n')
        pseudonymized_lines = []
        
        for line in lines:
            if line.startswith('PID|'):  # Patient Identification segment
                pseudonymized_lines.append(self._pseudonymize_pid_segment(line))
            elif line.startswith('OBR|'):  # Observation Request segment
                pseudonymized_lines.append(self._pseudonymize_obr_segment(line))
            else:
                pseudonymized_lines.append(line)
        
        return '\n'.join(pseudonymized_lines)
    
    def _pseudonymize_pid_segment(self, pid_segment: str) -> str:
        """Pseudonymize identifiers in PID segment."""
        fields = pid_segment.split('|')
        
        # PID.3 - Patient Identifier List
        if len(fields) > 3 and fields[3]:
            # Handle multiple identifiers separated by ~
            identifiers = fields[3].split('~')
            pseudonymized_identifiers = []
            
            for identifier in identifiers:
                components = identifier.split('^')
                if len(components) > 0 and components[0]:
                    # Determine identifier type from component 5 (identifier type code)
                    id_type = components[4] if len(components) > 4 else "Patient"
                    components[0] = self.pseudonymize_identifier(components[0], id_type)
                pseudonymized_identifiers.append('^'.join(components))
            
            fields[3] = '~'.join(pseudonymized_identifiers)
        
        # PID.18 - Patient Account Number
        if len(fields) > 18 and fields[18]:
            fields[18] = self.pseudonymize_identifier(fields[18], "Patient")
        
        return '|'.join(fields)
    
    def _pseudonymize_obr_segment(self, obr_segment: str) -> str:
        """Pseudonymize identifiers in OBR segment."""
        fields = obr_segment.split('|')
        
        # OBR.3 - Filler Order Number (often contains patient reference)
        if len(fields) > 3 and fields[3]:
            fields[3] = self.pseudonymize_identifier(fields[3], "specimen_id")
        
        return '|'.join(fields)
    
    def pseudonymize_json_data(self, data: Union[Dict, List, Any]) -> Any:
        """
        Pseudonymize identifiers in generic JSON data.
        
        Args:
            data: JSON data structure
        
        Returns:
            Data with pseudonymized identifiers
        """
        if isinstance(data, dict):
            import copy
            pseudonymized_data = copy.deepcopy(data)
            
            for key, value in pseudonymized_data.items():
                if self._is_identifier_field(key):
                    if isinstance(value, str):
                        id_type = self._get_id_type_from_field_name(key)
                        pseudonymized_data[key] = self.pseudonymize_identifier(value, id_type)
                elif isinstance(value, (dict, list)):
                    pseudonymized_data[key] = self.pseudonymize_json_data(value)
            
            return pseudonymized_data
        
        elif isinstance(data, list):
            return [self.pseudonymize_json_data(item) for item in data]
        
        else:
            return data
    
    def _is_identifier_field(self, field_name: str) -> bool:
        """Check if field name indicates a patient identifier."""
        field_lower = field_name.lower()
        identifier_patterns = [
            r'patient.*id', r'patient.*identifier', r'patientid',
            r'mrn', r'medical.*record', r'ssn', r'social.*security',
            r'specimen.*id', r'subject', r'reference'
        ]
        
        for pattern in identifier_patterns:
            if re.search(pattern, field_lower):
                return True
        
        return field_name in self.config.supported_id_types
    
    def _get_id_type_from_field_name(self, field_name: str) -> str:
        """Determine identifier type from field name."""
        field_lower = field_name.lower()
        
        if 'mrn' in field_lower or 'medical' in field_lower:
            return "MRN"
        elif 'ssn' in field_lower or 'social' in field_lower:
            return "SSN"
        elif 'specimen' in field_lower:
            return "specimen_id"
        elif 'subject' in field_lower or 'reference' in field_lower:
            return "subject"
        else:
            return "Patient"
    
    def _save_mapping(self, mapping: IdentifierMapping):
        """Persist identifier mapping to storage."""
        try:
            mapping_file = self.config.storage_path / f"mapping_{mapping.pseudonymized_id}.json"
            mapping_data = {
                "original_id": mapping.original_id,
                "pseudonymized_id": mapping.pseudonymized_id,
                "identifier_type": mapping.identifier_type,
                "created_at": mapping.created_at,
                "last_accessed": mapping.last_accessed,
                "access_count": mapping.access_count
            }
            
            content = json.dumps(mapping_data, indent=2)
            
            # Encrypt if cipher suite available
            if self._cipher_suite:
                content = self._cipher_suite.encrypt(content.encode()).decode()
            
            with open(mapping_file, 'w') as f:
                f.write(content)
                
        except Exception as e:
            logger.error(f"Failed to save mapping: {e}")
    
    def _load_mappings(self):
        """Load existing identifier mappings from storage."""
        try:
            mapping_files = list(self.config.storage_path.glob("mapping_*.json"))
            
            for mapping_file in mapping_files:
                try:
                    with open(mapping_file, 'r') as f:
                        content = f.read()
                    
                    # Decrypt if cipher suite available
                    if self._cipher_suite:
                        content = self._cipher_suite.decrypt(content.encode()).decode()
                    
                    mapping_data = json.loads(content)
                    
                    mapping = IdentifierMapping(
                        original_id=mapping_data["original_id"],
                        pseudonymized_id=mapping_data["pseudonymized_id"],
                        identifier_type=mapping_data["identifier_type"],
                        created_at=mapping_data["created_at"],
                        last_accessed=mapping_data["last_accessed"],
                        access_count=mapping_data.get("access_count", 0)
                    )
                    
                    cache_key = f"{mapping.identifier_type}:{mapping.original_id}"
                    self._mapping_cache[cache_key] = mapping
                    self._reverse_mapping[mapping.pseudonymized_id] = mapping.original_id
                    
                except Exception as e:
                    logger.error(f"Failed to load mapping from {mapping_file}: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Failed to load mappings: {e}")
    
    def get_pseudonymization_stats(self) -> Dict[str, Any]:
        """Get statistics about pseudonymization service."""
        type_counts = {}
        for mapping in self._mapping_cache.values():
            type_counts[mapping.identifier_type] = type_counts.get(mapping.identifier_type, 0) + 1
        
        return {
            "total_mappings": len(self._mapping_cache),
            "type_breakdown": type_counts,
            "encryption_enabled": self._cipher_suite is not None,
            "storage_path": str(self.config.storage_path)
        }
    
    def clear_mappings(self, older_than_days: Optional[int] = None) -> int:
        """
        Clear identifier mappings, optionally filtered by age.
        
        Args:
            older_than_days: Only clear mappings older than this many days
        
        Returns:
            Number of mappings cleared
        """
        if older_than_days is None:
            # Clear all mappings
            cleared_count = len(self._mapping_cache)
            self._mapping_cache.clear()
            self._reverse_mapping.clear()
            
            # Remove files
            for mapping_file in self.config.storage_path.glob("mapping_*.json"):
                mapping_file.unlink()
            
            logger.info(f"Cleared all {cleared_count} pseudonymization mappings")
            return cleared_count
        
        else:
            # Clear old mappings
            from datetime import timedelta
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=older_than_days)
            
            to_remove = []
            for cache_key, mapping in self._mapping_cache.items():
                created_date = datetime.fromisoformat(mapping.created_at.replace('Z', '+00:00'))
                if created_date < cutoff_date:
                    to_remove.append((cache_key, mapping.pseudonymized_id))
            
            # Remove from caches and files
            for cache_key, pseudonymized_id in to_remove:
                del self._mapping_cache[cache_key]
                if pseudonymized_id in self._reverse_mapping:
                    del self._reverse_mapping[pseudonymized_id]
                
                mapping_file = self.config.storage_path / f"mapping_{pseudonymized_id}.json"
                if mapping_file.exists():
                    mapping_file.unlink()
            
            logger.info(f"Cleared {len(to_remove)} pseudonymization mappings older than {older_than_days} days")
            return len(to_remove)