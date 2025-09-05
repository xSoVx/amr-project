from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


Decision = Literal["S", "I", "R", "RR"]
Method = Literal["MIC", "DISC"]


class ClassificationInput(BaseModel):
    organism: Optional[str] = None
    organism_snomed: Optional[str] = None
    antibiotic: Optional[str] = None
    antibiotic_atc: Optional[str] = None
    method: Optional[Method] = None
    mic_mg_L: Optional[float] = None
    disc_zone_mm: Optional[float] = None
    specimenId: Optional[str] = None
    patientId: Optional[str] = None
    features: Dict[str, Any] = Field(default_factory=dict)


class ClassificationResult(BaseModel):
    specimenId: Optional[str] = None
    organism: Optional[str] = None
    antibiotic: Optional[str] = None
    method: Optional[Method] = None
    input: Dict[str, Any]
    decision: Decision
    reason: str
    ruleVersion: Optional[str] = None


class OperationOutcomeIssue(BaseModel):
    severity: Literal["error", "warning"] = "error"
    code: str = "invalid"
    diagnostics: str
    expression: Optional[List[str]] = None


class OperationOutcome(BaseModel):
    resourceType: Literal["OperationOutcome"] = "OperationOutcome"
    issue: List[OperationOutcomeIssue]

