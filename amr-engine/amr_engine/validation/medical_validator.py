"""
Medical Data Validation for AMR Classification System

This module provides comprehensive input validation for medical data used in
antimicrobial resistance classification, ensuring data integrity, security,
and clinical accuracy.

Key Features:
- Pydantic-based validation with medical context awareness
- SNOMED CT and ATC code validation
- Injection attack prevention
- Clinical range validation for MIC values and zone diameters
- Breakpoint standard compliance checking
"""

import re
import logging
from typing import Optional, List, Dict, Any, Union, Set
from enum import Enum
from decimal import Decimal, InvalidOperation
from pydantic import BaseModel, Field, validator, ValidationError, root_validator

logger = logging.getLogger(__name__)


class TestMethod(str, Enum):
    """Validated testing methods for AMR"""
    DISK_DIFFUSION = "disk_diffusion"
    MIC = "mic"
    ETEST = "etest"
    GRADIENT_DIFFUSION = "gradient_diffusion"
    AUTOMATED_SYSTEM = "automated_system"


class BreakpointStandard(str, Enum):
    """Validated breakpoint interpretation standards"""
    EUCAST = "EUCAST"
    CLSI = "CLSI"
    BSAC = "BSAC"


class SusceptibilityResult(str, Enum):
    """Validated susceptibility results"""
    SUSCEPTIBLE = "S"
    INTERMEDIATE = "I"
    RESISTANT = "R"
    INSUFFICIENT_EVIDENCE = "IE"
    NON_SUSCEPTIBLE = "NS"
    SUSCEPTIBLE_DOSE_DEPENDENT = "SDD"


class OrganismValidator:
    """
    Organism name validation with SNOMED CT awareness
    """
    
    # Common pathogenic organisms with validation patterns
    VALIDATED_ORGANISMS = {
        "staphylococcus aureus": {"snomed": "3092008", "gram": "positive"},
        "escherichia coli": {"snomed": "112283007", "gram": "negative"}, 
        "klebsiella pneumoniae": {"snomed": "56415008", "gram": "negative"},
        "pseudomonas aeruginosa": {"snomed": "52499004", "gram": "negative"},
        "enterococcus faecalis": {"snomed": "78065002", "gram": "positive"},
        "acinetobacter baumannii": {"snomed": "788707008", "gram": "negative"},
        "streptococcus pneumoniae": {"snomed": "9861002", "gram": "positive"},
        "enterobacter cloacae": {"snomed": "40886007", "gram": "negative"},
        "proteus mirabilis": {"snomed": "35408001", "gram": "negative"},
        "citrobacter freundii": {"snomed": "42542002", "gram": "negative"}
    }
    
    # Suspicious patterns that might indicate injection attempts
    SUSPICIOUS_PATTERNS = [
        r'[<>"\']',                    # HTML/XML injection characters
        r'(script|javascript|vbscript)', # Script injection
        r'(union|select|insert|update|delete|drop)', # SQL injection
        r'(\$\{|\#\{)',               # Expression language injection
        r'(\\x[0-9a-fA-F]{2})',       # Hexadecimal encoding
        r'(%[0-9a-fA-F]{2})',         # URL encoding
        r'(\.\.\/|\.\.\\)',           # Path traversal
    ]
    
    @classmethod
    def validate_organism_name(cls, organism: str) -> str:
        """
        Validate and sanitize organism name
        
        Args:
            organism: Raw organism name input
            
        Returns:
            Validated and cleaned organism name
            
        Raises:
            ValueError: If organism name is invalid or suspicious
        """
        if not organism or not isinstance(organism, str):
            raise ValueError("Organism name cannot be empty")
        
        # Remove leading/trailing whitespace and normalize
        cleaned = organism.strip().lower()
        
        if not cleaned:
            raise ValueError("Organism name cannot be empty after cleaning")
        
        if len(cleaned) > 200:
            raise ValueError("Organism name too long (max 200 characters)")
        
        if len(cleaned) < 2:
            raise ValueError("Organism name too short (min 2 characters)")
        
        # Check for suspicious patterns
        for pattern in cls.SUSPICIOUS_PATTERNS:
            if re.search(pattern, cleaned, re.IGNORECASE):
                logger.warning(f"Suspicious pattern detected in organism name: {pattern}")
                raise ValueError("Invalid characters in organism name")
        
        # Validate against known organisms or basic scientific naming pattern
        if cleaned in cls.VALIDATED_ORGANISMS:
            return cls.VALIDATED_ORGANISMS[cleaned].get("display_name", cleaned)
        
        # Check for basic scientific naming pattern (genus species)
        scientific_pattern = r'^[a-z][a-z\s]+[a-z]$'
        if not re.match(scientific_pattern, cleaned):
            logger.warning(f"Organism name doesn't match scientific naming pattern: {cleaned}")
        
        # Additional validation: check for minimum viable organism name structure
        if not re.match(r'^[a-z][a-z\s\-\.]+$', cleaned):
            raise ValueError("Organism name contains invalid characters")
        
        # Check for excessive whitespace or special characters
        if re.search(r'\s{2,}|[^\w\s\-\.]', cleaned):
            raise ValueError("Organism name formatting is invalid")
        
        return cleaned.title()  # Return in Title Case
    
    @classmethod
    def get_organism_metadata(cls, organism: str) -> Dict[str, Any]:
        """Get additional metadata for validated organisms"""
        cleaned = organism.lower().strip()
        return cls.VALIDATED_ORGANISMS.get(cleaned, {})


class AntibioticValidator:
    """
    Antibiotic name validation with ATC code awareness
    """
    
    # Common antibiotics with ATC codes and metadata
    VALIDATED_ANTIBIOTICS = {
        "amoxicillin": {"atc": "J01CA04", "class": "penicillin", "route": "oral"},
        "ciprofloxacin": {"atc": "J01MA02", "class": "fluoroquinolone", "route": "oral/iv"},
        "vancomycin": {"atc": "J01XA01", "class": "glycopeptide", "route": "iv"},
        "meropenem": {"atc": "J01DH02", "class": "carbapenem", "route": "iv"},
        "ceftriaxone": {"atc": "J01DD04", "class": "cephalosporin", "route": "iv"},
        "gentamicin": {"atc": "J01GB03", "class": "aminoglycoside", "route": "iv"},
        "clindamycin": {"atc": "J01FF01", "class": "lincosamide", "route": "oral/iv"},
        "doxycycline": {"atc": "J01AA02", "class": "tetracycline", "route": "oral"},
        "trimethoprim": {"atc": "J01EA01", "class": "folate antagonist", "route": "oral"},
        "azithromycin": {"atc": "J01FA10", "class": "macrolide", "route": "oral"}
    }
    
    @classmethod
    def validate_antibiotic_name(cls, antibiotic: str) -> str:
        """
        Validate and sanitize antibiotic name
        
        Args:
            antibiotic: Raw antibiotic name input
            
        Returns:
            Validated and cleaned antibiotic name
            
        Raises:
            ValueError: If antibiotic name is invalid or suspicious
        """
        if not antibiotic or not isinstance(antibiotic, str):
            raise ValueError("Antibiotic name cannot be empty")
        
        # Remove leading/trailing whitespace and normalize
        cleaned = antibiotic.strip().lower()
        
        if not cleaned:
            raise ValueError("Antibiotic name cannot be empty after cleaning")
        
        if len(cleaned) > 100:
            raise ValueError("Antibiotic name too long (max 100 characters)")
        
        if len(cleaned) < 2:
            raise ValueError("Antibiotic name too short (min 2 characters)")
        
        # Check for suspicious patterns (reuse from OrganismValidator)
        for pattern in OrganismValidator.SUSPICIOUS_PATTERNS:
            if re.search(pattern, cleaned, re.IGNORECASE):
                logger.warning(f"Suspicious pattern detected in antibiotic name: {pattern}")
                raise ValueError("Invalid characters in antibiotic name")
        
        # Validate basic antibiotic naming pattern
        if not re.match(r'^[a-z][a-z\-\s]+$', cleaned):
            raise ValueError("Antibiotic name contains invalid characters")
        
        # Return known antibiotic or cleaned input
        if cleaned in cls.VALIDATED_ANTIBIOTICS:
            return cleaned.capitalize()
        
        return cleaned.title()
    
    @classmethod
    def get_antibiotic_metadata(cls, antibiotic: str) -> Dict[str, Any]:
        """Get additional metadata for validated antibiotics"""
        cleaned = antibiotic.lower().strip()
        return cls.VALIDATED_ANTIBIOTICS.get(cleaned, {})


class AMRClassificationRequest(BaseModel):
    """
    Validated AMR classification request with comprehensive input validation
    
    This model ensures all inputs for AMR classification are properly validated,
    sanitized, and conform to clinical standards.
    """
    
    # Required fields
    organism: str = Field(
        ...,
        min_length=2,
        max_length=200,
        description="Organism name (will be validated against SNOMED CT patterns)"
    )
    
    antibiotic: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="Antibiotic name (will be validated against ATC patterns)"
    )
    
    method: TestMethod = Field(
        ...,
        description="Testing method used for susceptibility determination"
    )
    
    breakpoint_standard: BreakpointStandard = Field(
        ...,
        description="Breakpoint standard used for interpretation"
    )
    
    # Optional quantitative results
    mic_value: Optional[float] = Field(
        None,
        ge=0.001,
        le=1024.0,
        description="MIC value in mg/L (0.001-1024 range)"
    )
    
    zone_diameter: Optional[int] = Field(
        None,
        ge=6,
        le=100,
        description="Zone diameter in mm (6-100 range)"
    )
    
    # Optional metadata
    specimen_id: Optional[str] = Field(
        None,
        max_length=50,
        regex=r'^[A-Za-z0-9\-_\.]+$',
        description="Specimen identifier (alphanumeric, dash, underscore, dot only)"
    )
    
    patient_id: Optional[str] = Field(
        None,
        max_length=50,
        regex=r'^[A-Za-z0-9\-_\.]+$',
        description="Patient identifier (alphanumeric, dash, underscore, dot only)"
    )
    
    laboratory_id: Optional[str] = Field(
        None,
        max_length=50,
        regex=r'^[A-Za-z0-9\-_\.]+$',
        description="Laboratory identifier"
    )
    
    test_date: Optional[str] = Field(
        None,
        regex=r'^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2}.*)?$',
        description="Test date in ISO format"
    )
    
    # Additional clinical context
    clinical_indication: Optional[str] = Field(
        None,
        max_length=500,
        description="Clinical indication for testing"
    )
    
    priority: Optional[str] = Field(
        "routine",
        regex=r'^(routine|urgent|stat)$',
        description="Test priority level"
    )
    
    @validator('organism', pre=True)
    def validate_organism_field(cls, v):
        """Validate organism using OrganismValidator"""
        if v is None:
            raise ValueError("Organism is required")
        return OrganismValidator.validate_organism_name(v)
    
    @validator('antibiotic', pre=True) 
    def validate_antibiotic_field(cls, v):
        """Validate antibiotic using AntibioticValidator"""
        if v is None:
            raise ValueError("Antibiotic is required")
        return AntibioticValidator.validate_antibiotic_name(v)
    
    @validator('mic_value')
    def validate_mic_value_precision(cls, v):
        """Validate MIC value precision and clinical ranges"""
        if v is None:
            return v
        
        try:
            # Convert to Decimal for precise validation
            decimal_value = Decimal(str(v))
            
            # Check precision (max 3 decimal places for MIC)
            if decimal_value.as_tuple().exponent < -3:
                raise ValueError("MIC value has too many decimal places (max 3)")
            
            # Validate clinical ranges - common MIC ranges
            if decimal_value < Decimal('0.001'):
                raise ValueError("MIC value too low (minimum 0.001 mg/L)")
            
            if decimal_value > Decimal('1024'):
                raise ValueError("MIC value too high (maximum 1024 mg/L)")
            
            # Check for common MIC dilution series values
            common_mics = [0.001, 0.002, 0.004, 0.008, 0.015, 0.03, 0.06, 0.125, 0.25, 0.5, 1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024]
            if float(decimal_value) not in common_mics:
                logger.info(f"Unusual MIC value not in common dilution series: {v}")
            
            return float(v)
            
        except (InvalidOperation, TypeError):
            raise ValueError("Invalid MIC value format")
    
    @validator('zone_diameter')
    def validate_zone_diameter_range(cls, v):
        """Validate zone diameter clinical ranges"""
        if v is None:
            return v
        
        # Clinical zone diameter ranges (disk diffusion)
        if v < 6:
            raise ValueError("Zone diameter too small (minimum 6mm)")
        
        if v > 100:
            raise ValueError("Zone diameter too large (maximum 100mm)")
        
        # Zone diameters should be integers
        if not isinstance(v, int):
            raise ValueError("Zone diameter must be an integer")
        
        return v
    
    @validator('clinical_indication', pre=True)
    def validate_clinical_indication(cls, v):
        """Validate clinical indication text"""
        if v is None:
            return v
        
        if not isinstance(v, str):
            raise ValueError("Clinical indication must be text")
        
        # Remove potential injection patterns
        cleaned = re.sub(r'[<>"\']', '', v.strip())
        
        if len(cleaned) > 500:
            raise ValueError("Clinical indication too long (max 500 characters)")
        
        # Check for suspicious patterns
        for pattern in OrganismValidator.SUSPICIOUS_PATTERNS:
            if re.search(pattern, cleaned, re.IGNORECASE):
                raise ValueError("Invalid characters in clinical indication")
        
        return cleaned
    
    @root_validator
    def validate_method_result_consistency(cls, values):
        """Validate consistency between method and provided results"""
        method = values.get('method')
        mic_value = values.get('mic_value')
        zone_diameter = values.get('zone_diameter')
        
        if method in [TestMethod.MIC, TestMethod.ETEST, TestMethod.AUTOMATED_SYSTEM]:
            if mic_value is None:
                logger.warning(f"MIC method {method} specified but no MIC value provided")
        
        if method == TestMethod.DISK_DIFFUSION:
            if zone_diameter is None:
                logger.warning("Disk diffusion method specified but no zone diameter provided")
        
        # Validate that at least one quantitative result is provided
        if mic_value is None and zone_diameter is None:
            raise ValueError("Either MIC value or zone diameter must be provided")
        
        return values
    
    def get_validation_summary(self) -> Dict[str, Any]:
        """Get summary of validation results and metadata"""
        organism_meta = OrganismValidator.get_organism_metadata(self.organism)
        antibiotic_meta = AntibioticValidator.get_antibiotic_metadata(self.antibiotic)
        
        return {
            "validated": True,
            "organism": {
                "name": self.organism,
                "metadata": organism_meta
            },
            "antibiotic": {
                "name": self.antibiotic,
                "metadata": antibiotic_meta
            },
            "quantitative_data": {
                "mic_provided": self.mic_value is not None,
                "zone_provided": self.zone_diameter is not None,
                "mic_value": self.mic_value,
                "zone_diameter": self.zone_diameter
            },
            "method": self.method.value,
            "standard": self.breakpoint_standard.value
        }


class BulkClassificationRequest(BaseModel):
    """
    Validated bulk classification request for multiple isolates
    """
    
    requests: List[AMRClassificationRequest] = Field(
        ...,
        min_items=1,
        max_items=1000,  # Limit bulk requests to prevent DoS
        description="List of classification requests"
    )
    
    batch_id: Optional[str] = Field(
        None,
        max_length=50,
        regex=r'^[A-Za-z0-9\-_\.]+$',
        description="Batch identifier for tracking"
    )
    
    priority: Optional[str] = Field(
        "routine",
        regex=r'^(routine|urgent|stat)$',
        description="Batch priority level"
    )
    
    @validator('requests')
    def validate_batch_consistency(cls, v):
        """Validate consistency across batch requests"""
        if not v:
            raise ValueError("At least one request is required")
        
        # Check for duplicate specimen IDs within batch
        specimen_ids = [req.specimen_id for req in v if req.specimen_id]
        if len(specimen_ids) != len(set(specimen_ids)):
            raise ValueError("Duplicate specimen IDs found in batch")
        
        return v


# Additional validation utilities

def validate_snomed_code(code: str) -> bool:
    """Validate SNOMED CT code format"""
    # Basic SNOMED CT code validation (numeric, 6-18 digits)
    return bool(re.match(r'^\d{6,18}$', code))


def validate_atc_code(code: str) -> bool:
    """Validate ATC code format"""
    # Basic ATC code validation (A-N followed by 2 digits, 1 letter, 2 digits)
    return bool(re.match(r'^[A-N]\d{2}[A-Z]{2}\d{2}$', code))


def sanitize_medical_text(text: str, max_length: int = 500) -> str:
    """
    Sanitize medical text input for safe storage and display
    
    Args:
        text: Input text to sanitize
        max_length: Maximum allowed length
        
    Returns:
        Sanitized text
        
    Raises:
        ValueError: If text contains suspicious patterns
    """
    if not text:
        return ""
    
    # Remove potentially dangerous characters
    cleaned = re.sub(r'[<>"\']', '', text.strip())
    
    if len(cleaned) > max_length:
        raise ValueError(f"Text too long (max {max_length} characters)")
    
    # Check for suspicious patterns
    for pattern in OrganismValidator.SUSPICIOUS_PATTERNS:
        if re.search(pattern, cleaned, re.IGNORECASE):
            raise ValueError("Invalid characters in text input")
    
    return cleaned