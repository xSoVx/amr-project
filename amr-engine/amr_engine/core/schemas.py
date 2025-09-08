from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


Decision = Literal["S", "I", "R", "RR", "Requires Review"]
Method = Literal["MIC", "DISC"]


class ClassificationInput(BaseModel):
    """
    Input data for AMR classification.
    
    Either organism or organism_snomed must be provided.
    Either antibiotic or antibiotic_atc must be provided.
    Method must be specified along with corresponding measurement.
    """
    organism: Optional[str] = Field(
        None, 
        description="Organism name (e.g., 'Escherichia coli', 'Staphylococcus aureus')",
        examples=["Escherichia coli", "Staphylococcus aureus", "Klebsiella pneumoniae"]
    )
    organism_snomed: Optional[str] = Field(
        None,
        description="SNOMED CT code for organism",
        examples=["112283007", "3092008"]
    )
    antibiotic: Optional[str] = Field(
        None,
        description="Antibiotic name (e.g., 'Amoxicillin', 'Ciprofloxacin')",
        examples=["Amoxicillin", "Ciprofloxacin", "Gentamicin", "Vancomycin"]
    )
    antibiotic_atc: Optional[str] = Field(
        None,
        description="ATC code for antibiotic",
        examples=["J01CA04", "J01MA02"]
    )
    method: Optional[Method] = Field(
        None,
        description="Test method: MIC (minimum inhibitory concentration) or DISC (disc diffusion)"
    )
    mic_mg_L: Optional[float] = Field(
        None,
        description="MIC value in mg/L (required when method=MIC)",
        examples=[0.5, 1.0, 4.0, 16.0],
        ge=0
    )
    disc_zone_mm: Optional[float] = Field(
        None, 
        description="Disc diffusion zone diameter in mm (required when method=DISC)",
        examples=[15.0, 22.0, 28.0, 35.0],
        ge=0
    )
    specimenId: Optional[str] = Field(
        None,
        description="Unique specimen identifier",
        examples=["SPEC-001", "LAB-2024-001234"]
    )
    patientId: Optional[str] = Field(
        None,
        description="Patient identifier", 
        examples=["PT-001", "12345678"]
    )
    features: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata and features for classification"
    )
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "organism": "Escherichia coli",
                    "antibiotic": "Amoxicillin",
                    "method": "MIC",
                    "mic_mg_L": 4.0,
                    "specimenId": "SPEC-001"
                },
                {
                    "organism": "Staphylococcus aureus", 
                    "antibiotic": "Ciprofloxacin",
                    "method": "DISC",
                    "disc_zone_mm": 20.0,
                    "specimenId": "SPEC-002"
                }
            ]
        }
    }


class ClassificationResult(BaseModel):
    """
    AMR classification result with decision and reasoning.
    
    Contains the classification decision (S/I/R/RR) along with 
    the reasoning behind the decision and input data used.
    """
    specimenId: Optional[str] = Field(
        None,
        description="Specimen identifier from input data",
        examples=["SPEC-001", "LAB-2024-001234"]
    )
    organism: Optional[str] = Field(
        None,
        description="Organism name from classification",
        examples=["Escherichia coli", "Staphylococcus aureus"]
    )
    antibiotic: Optional[str] = Field(
        None,
        description="Antibiotic name from classification", 
        examples=["Amoxicillin", "Ciprofloxacin"]
    )
    method: Optional[Method] = Field(
        None,
        description="Test method used (MIC or DISC)"
    )
    input: Dict[str, Any] = Field(
        description="Original input data used for classification"
    )
    decision: Decision = Field(
        description="Classification decision: S=Susceptible, I=Susceptible increased exposure, R=Resistant, RR=Resistant rare resistance"
    )
    reason: str = Field(
        description="Human-readable explanation of the classification decision",
        examples=[
            "MIC 4.0 mg/L <= breakpoint 8.0 mg/L",
            "Zone 15 mm < breakpoint 20 mm", 
            "No applicable breakpoint found"
        ]
    )
    ruleVersion: Optional[str] = Field(
        None,
        description="Version of classification rules used",
        examples=["EUCAST v2025.1", "CLSI 2024"]
    )
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "specimenId": "SPEC-001",
                    "organism": "Escherichia coli",
                    "antibiotic": "Amoxicillin",
                    "method": "MIC",
                    "input": {
                        "organism": "Escherichia coli",
                        "antibiotic": "Amoxicillin", 
                        "method": "MIC",
                        "mic_mg_L": 4.0,
                        "specimenId": "SPEC-001"
                    },
                    "decision": "S",
                    "reason": "MIC 4.0 mg/L <= breakpoint 8.0 mg/L",
                    "ruleVersion": "EUCAST v2025.1"
                },
                {
                    "specimenId": "SPEC-002", 
                    "organism": "Staphylococcus aureus",
                    "antibiotic": "Ciprofloxacin",
                    "method": "DISC",
                    "input": {
                        "organism": "Staphylococcus aureus",
                        "antibiotic": "Ciprofloxacin",
                        "method": "DISC",
                        "disc_zone_mm": 15.0,
                        "specimenId": "SPEC-002"
                    },
                    "decision": "R",
                    "reason": "Zone 15 mm < breakpoint 20 mm",
                    "ruleVersion": "EUCAST v2025.1"
                }
            ]
        }
    }


class OperationOutcomeIssue(BaseModel):
    severity: Literal["error", "warning"] = "error"
    code: str = "invalid"
    diagnostics: str
    expression: Optional[List[str]] = None


class OperationOutcome(BaseModel):
    resourceType: Literal["OperationOutcome"] = "OperationOutcome"
    issue: List[OperationOutcomeIssue]


class ProblemDetails(BaseModel):
    """
    RFC 7807 Problem Details for HTTP APIs.
    """
    type: Optional[str] = Field(
        "about:blank",
        description="A URI reference that identifies the problem type"
    )
    title: Optional[str] = Field(
        None,
        description="A short, human-readable summary of the problem type"
    )
    status: Optional[int] = Field(
        None,
        description="The HTTP status code"
    )
    detail: Optional[str] = Field(
        None,
        description="A human-readable explanation specific to this occurrence"
    )
    instance: Optional[str] = Field(
        None,
        description="A URI reference that identifies the specific occurrence"
    )
    # FHIR OperationOutcome embedded for healthcare context
    operationOutcome: Optional[OperationOutcome] = Field(
        None,
        description="Embedded FHIR OperationOutcome for detailed error information"
    )
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "type": "https://amr-engine.com/problems/validation-error",
                    "title": "Validation Error",
                    "status": 400,
                    "detail": "Input validation failed for classification request",
                    "operationOutcome": {
                        "resourceType": "OperationOutcome",
                        "issue": [{
                            "severity": "error",
                            "code": "invalid",
                            "diagnostics": "Missing required field: organism"
                        }]
                    }
                }
            ]
        }
    }

