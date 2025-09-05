from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
from pydantic import BaseModel, Field
from .terminology import terminology_service, TerminologyValidationResult

logger = logging.getLogger(__name__)


class CodeableConcept(BaseModel):
    coding: List[Dict[str, Any]] = Field(default_factory=list)
    text: Optional[str] = None


class Coding(BaseModel):
    system: Optional[str] = None
    code: Optional[str] = None
    display: Optional[str] = None


class Reference(BaseModel):
    reference: Optional[str] = None
    display: Optional[str] = None


class Identifier(BaseModel):
    use: Optional[str] = None
    system: Optional[str] = None
    value: Optional[str] = None


class Quantity(BaseModel):
    value: Optional[float] = None
    unit: Optional[str] = None
    system: Optional[str] = None
    code: Optional[str] = None


class FHIRPatient(BaseModel):
    resourceType: str = "Patient"
    id: Optional[str] = None
    identifier: List[Identifier] = Field(default_factory=list)
    active: Optional[bool] = True
    name: List[Dict[str, Any]] = Field(default_factory=list)
    gender: Optional[str] = None
    birthDate: Optional[str] = None


class FHIRSpecimen(BaseModel):
    resourceType: str = "Specimen"
    id: Optional[str] = None
    identifier: List[Identifier] = Field(default_factory=list)
    status: Optional[str] = None
    type: Optional[CodeableConcept] = None
    subject: Optional[Reference] = None
    receivedTime: Optional[str] = None
    collection: Optional[Dict[str, Any]] = None
    container: List[Dict[str, Any]] = Field(default_factory=list)


class FHIRObservation(BaseModel):
    resourceType: str = "Observation"
    id: Optional[str] = None
    identifier: List[Identifier] = Field(default_factory=list)
    status: str
    category: List[CodeableConcept] = Field(default_factory=list)
    code: CodeableConcept
    subject: Optional[Reference] = None
    encounter: Optional[Reference] = None
    effectiveDateTime: Optional[str] = None
    issued: Optional[str] = None
    performer: List[Reference] = Field(default_factory=list)
    valueQuantity: Optional[Quantity] = None
    valueCodeableConcept: Optional[CodeableConcept] = None
    valueString: Optional[str] = None
    interpretation: List[CodeableConcept] = Field(default_factory=list)
    note: List[Dict[str, str]] = Field(default_factory=list)
    bodySite: Optional[CodeableConcept] = None
    method: Optional[CodeableConcept] = None
    specimen: Optional[Reference] = None
    device: Optional[Reference] = None
    referenceRange: List[Dict[str, Any]] = Field(default_factory=list)
    hasMember: List[Reference] = Field(default_factory=list)
    derivedFrom: List[Reference] = Field(default_factory=list)
    component: List[Dict[str, Any]] = Field(default_factory=list)


class FHIRDiagnosticReport(BaseModel):
    resourceType: str = "DiagnosticReport"
    id: Optional[str] = None
    identifier: List[Identifier] = Field(default_factory=list)
    basedOn: List[Reference] = Field(default_factory=list)
    status: str
    category: List[CodeableConcept] = Field(default_factory=list)
    code: CodeableConcept
    subject: Optional[Reference] = None
    encounter: Optional[Reference] = None
    effectiveDateTime: Optional[str] = None
    effectivePeriod: Optional[Dict[str, str]] = None
    issued: Optional[str] = None
    performer: List[Reference] = Field(default_factory=list)
    resultsInterpreter: List[Reference] = Field(default_factory=list)
    specimen: List[Reference] = Field(default_factory=list)
    result: List[Reference] = Field(default_factory=list)
    imagingStudy: List[Reference] = Field(default_factory=list)
    media: List[Dict[str, Any]] = Field(default_factory=list)
    conclusion: Optional[str] = None
    conclusionCode: List[CodeableConcept] = Field(default_factory=list)
    presentedForm: List[Dict[str, Any]] = Field(default_factory=list)


class FHIRBundle(BaseModel):
    resourceType: str = "Bundle"
    id: Optional[str] = None
    identifier: Optional[Identifier] = None
    type: str
    timestamp: Optional[str] = None
    total: Optional[int] = None
    link: List[Dict[str, str]] = Field(default_factory=list)
    entry: List[Dict[str, Any]] = Field(default_factory=list)


class FHIRValidator:
    """Comprehensive FHIR resource validation."""
    
    def __init__(self):
        self.errors: List[Dict[str, str]] = []
        self.warnings: List[Dict[str, str]] = []
    
    async def validate_bundle(self, bundle_data: Dict[str, Any]) -> bool:
        """Validate a FHIR Bundle resource."""
        self.errors.clear()
        self.warnings.clear()
        
        try:
            bundle = FHIRBundle(**bundle_data)
        except Exception as e:
            self.errors.append({
                "path": "/",
                "message": f"Invalid Bundle structure: {str(e)}",
                "severity": "error"
            })
            return False
        
        # Validate bundle type
        valid_types = ["document", "message", "transaction", "transaction-response", 
                      "batch", "batch-response", "history", "searchset", "collection"]
        if bundle.type not in valid_types:
            self.errors.append({
                "path": "/type",
                "message": f"Invalid bundle type: {bundle.type}",
                "severity": "error"
            })
        
        # Validate entries
        for i, entry in enumerate(bundle.entry):
            if not self._validate_bundle_entry(entry, i):
                return False
        
        return len(self.errors) == 0
    
    def _validate_bundle_entry(self, entry: Dict[str, Any], index: int) -> bool:
        """Validate individual bundle entry."""
        resource = entry.get("resource", {})
        resource_type = resource.get("resourceType")
        
        if not resource_type:
            self.errors.append({
                "path": f"/entry[{index}]/resource/resourceType",
                "message": "Missing resourceType",
                "severity": "error"
            })
            return False
        
        # Validate specific resource types
        if resource_type == "Observation":
            return self._validate_observation(resource, f"/entry[{index}]/resource")
        elif resource_type == "DiagnosticReport":
            return self._validate_diagnostic_report(resource, f"/entry[{index}]/resource")
        elif resource_type == "Patient":
            return self._validate_patient(resource, f"/entry[{index}]/resource")
        elif resource_type == "Specimen":
            return self._validate_specimen(resource, f"/entry[{index}]/resource")
        
        return True
    
    def _validate_observation(self, obs: Dict[str, Any], path: str) -> bool:
        """Validate FHIR Observation resource."""
        try:
            observation = FHIRObservation(**obs)
        except Exception as e:
            self.errors.append({
                "path": path,
                "message": f"Invalid Observation: {str(e)}",
                "severity": "error"
            })
            return False
        
        # Required fields validation
        if not observation.status:
            self.errors.append({
                "path": f"{path}/status",
                "message": "Missing required status field",
                "severity": "error"
            })
        
        if not observation.code:
            self.errors.append({
                "path": f"{path}/code",
                "message": "Missing required code field", 
                "severity": "error"
            })
        
        # Category validation for laboratory observations
        lab_category_found = False
        for cat in observation.category:
            for coding in cat.coding:
                if (coding.get("system") == "http://terminology.hl7.org/CodeSystem/observation-category" 
                    and coding.get("code") == "laboratory"):
                    lab_category_found = True
                    break
        
        if not lab_category_found:
            self.warnings.append({
                "path": f"{path}/category",
                "message": "Missing laboratory category",
                "severity": "warning"
            })
        
        # Value validation based on method
        method_text = None
        if observation.method:
            method_text = observation.method.text or (
                observation.method.coding[0].get("code") if observation.method.coding else None
            )
        
        if method_text:
            if method_text.upper() in ["MIC"] and not observation.valueQuantity:
                self.errors.append({
                    "path": f"{path}/valueQuantity",
                    "message": "MIC method requires valueQuantity",
                    "severity": "error"
                })
            elif method_text.upper() in ["DISC", "DISK"] and not observation.valueQuantity:
                self.errors.append({
                    "path": f"{path}/valueQuantity", 
                    "message": "Disc method requires valueQuantity",
                    "severity": "error"
                })
        
        return len([e for e in self.errors if e["path"].startswith(path)]) == 0
    
    async def _validate_snomed_codes(self, obs: Dict[str, Any], path: str):
        """Validate SNOMED CT codes against terminology server."""
        code = obs.get("code", {})
        for i, coding in enumerate(code.get("coding", [])):
            if coding.get("system") == "http://snomed.info/sct":
                validation = await terminology_service.validate_code(
                    system=coding.get("system"),
                    code=coding.get("code"),
                    display=coding.get("display")
                )
                
                if not validation.valid:
                    self.errors.append({
                        "path": f"{path}/code/coding[{i}]",
                        "message": f"Invalid SNOMED CT code: {validation.error}",
                        "severity": "error"
                    })
    
    def _validate_diagnostic_report(self, report: Dict[str, Any], path: str) -> bool:
        """Validate FHIR DiagnosticReport resource.""" 
        try:
            diagnostic_report = FHIRDiagnosticReport(**report)
        except Exception as e:
            self.errors.append({
                "path": path,
                "message": f"Invalid DiagnosticReport: {str(e)}",
                "severity": "error"
            })
            return False
        
        # Required fields
        required_fields = ["status", "code"]
        for field in required_fields:
            if not getattr(diagnostic_report, field, None):
                self.errors.append({
                    "path": f"{path}/{field}",
                    "message": f"Missing required field: {field}",
                    "severity": "error"
                })
        
        return len([e for e in self.errors if e["path"].startswith(path)]) == 0
    
    def _validate_patient(self, patient: Dict[str, Any], path: str) -> bool:
        """Validate FHIR Patient resource."""
        try:
            patient_resource = FHIRPatient(**patient)
        except Exception as e:
            self.errors.append({
                "path": path,
                "message": f"Invalid Patient: {str(e)}",
                "severity": "error"
            })
            return False
        
        return True
    
    def _validate_specimen(self, specimen: Dict[str, Any], path: str) -> bool:
        """Validate FHIR Specimen resource."""
        try:
            specimen_resource = FHIRSpecimen(**specimen)
        except Exception as e:
            self.errors.append({
                "path": path,
                "message": f"Invalid Specimen: {str(e)}",
                "severity": "error"
            })
            return False
        
        return True


class FHIRResourceExtractor:
    """Extract and organize FHIR resources from Bundle."""
    
    def __init__(self):
        self.patients: Dict[str, FHIRPatient] = {}
        self.specimens: Dict[str, FHIRSpecimen] = {}
        self.observations: Dict[str, FHIRObservation] = {}
        self.diagnostic_reports: Dict[str, FHIRDiagnosticReport] = {}
    
    def extract_from_bundle(self, bundle_data: Dict[str, Any]) -> bool:
        """Extract all resources from a FHIR Bundle."""
        try:
            bundle = FHIRBundle(**bundle_data)
            
            for entry in bundle.entry:
                resource = entry.get("resource", {})
                resource_type = resource.get("resourceType")
                resource_id = resource.get("id")
                
                if not resource_id:
                    continue
                
                if resource_type == "Patient":
                    self.patients[resource_id] = FHIRPatient(**resource)
                elif resource_type == "Specimen":
                    self.specimens[resource_id] = FHIRSpecimen(**resource)
                elif resource_type == "Observation":
                    self.observations[resource_id] = FHIRObservation(**resource)
                elif resource_type == "DiagnosticReport":
                    self.diagnostic_reports[resource_id] = FHIRDiagnosticReport(**resource)
            
            return True
        except Exception as e:
            logger.error(f"Failed to extract resources from bundle: {e}")
            return False
    
    def resolve_reference(self, reference: Optional[Reference]) -> Optional[Union[FHIRPatient, FHIRSpecimen, FHIRObservation, FHIRDiagnosticReport]]:
        """Resolve a FHIR reference to actual resource."""
        if not reference or not reference.reference:
            return None
        
        ref_parts = reference.reference.split("/")
        if len(ref_parts) != 2:
            return None
        
        resource_type, resource_id = ref_parts
        
        if resource_type == "Patient":
            return self.patients.get(resource_id)
        elif resource_type == "Specimen":
            return self.specimens.get(resource_id)
        elif resource_type == "Observation":
            return self.observations.get(resource_id)
        elif resource_type == "DiagnosticReport":
            return self.diagnostic_reports.get(resource_id)
        
        return None