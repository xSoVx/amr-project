"""
FHIR R4 AuditEvent resource builder for AMR classification results.

Converts AMR classification results into standards-compliant FHIR R4 AuditEvent
resources with proper agent, entity, and outcome information.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Union
from enum import Enum

from pydantic import BaseModel, Field


class AuditEventAction(str, Enum):
    """FHIR AuditEvent action codes."""
    CREATE = "C"
    READ = "R" 
    UPDATE = "U"
    DELETE = "D"
    EXECUTE = "E"


class AuditEventOutcome(str, Enum):
    """FHIR AuditEvent outcome codes."""
    SUCCESS = "0"
    MINOR_FAILURE = "4"
    SERIOUS_FAILURE = "8"
    MAJOR_FAILURE = "12"


class FHIRCoding(BaseModel):
    """FHIR Coding data type."""
    system: str
    code: str
    display: Optional[str] = None


class FHIRReference(BaseModel):
    """FHIR Reference data type."""
    reference: Optional[str] = None
    type: Optional[str] = None
    identifier: Optional[Dict[str, Any]] = None
    display: Optional[str] = None


class FHIRAuditEventAgent(BaseModel):
    """FHIR AuditEvent Agent component."""
    type: Optional[FHIRCoding] = None
    role: List[FHIRCoding] = Field(default_factory=list)
    who: Optional[FHIRReference] = None
    name: Optional[str] = None
    requestor: bool = False
    location: Optional[FHIRReference] = None
    policy: List[str] = Field(default_factory=list)
    media: Optional[FHIRCoding] = None
    network: Optional[Dict[str, Any]] = None
    purposeOfUse: List[FHIRCoding] = Field(default_factory=list)


class FHIRAuditEventSource(BaseModel):
    """FHIR AuditEvent Source component."""
    site: Optional[str] = None
    observer: FHIRReference
    type: List[FHIRCoding] = Field(default_factory=list)


class FHIRAuditEventEntity(BaseModel):
    """FHIR AuditEvent Entity component."""
    what: Optional[FHIRReference] = None
    type: Optional[FHIRCoding] = None
    role: Optional[FHIRCoding] = None
    lifecycle: Optional[FHIRCoding] = None
    securityLabel: List[FHIRCoding] = Field(default_factory=list)
    name: Optional[str] = None
    description: Optional[str] = None
    query: Optional[bytes] = None
    detail: List[Dict[str, Any]] = Field(default_factory=list)


class FHIRAuditEvent(BaseModel):
    """FHIR R4 AuditEvent resource."""
    resourceType: str = Field(default="AuditEvent")
    id: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None
    text: Optional[Dict[str, Any]] = None
    type: FHIRCoding
    subtype: List[FHIRCoding] = Field(default_factory=list)
    action: Optional[AuditEventAction] = None
    period: Optional[Dict[str, str]] = None
    recorded: str  # ISO 8601 datetime
    outcome: Optional[AuditEventOutcome] = None
    outcomeDesc: Optional[str] = None
    purposeOfEvent: List[FHIRCoding] = Field(default_factory=list)
    agent: List[FHIRAuditEventAgent]
    source: FHIRAuditEventSource
    entity: List[FHIRAuditEventEntity] = Field(default_factory=list)


class ClassificationResult(BaseModel):
    """AMR classification result data."""
    correlation_id: str
    patient_id: Optional[str] = None
    specimen_id: Optional[str] = None
    organism: Optional[str] = None
    antibiotics: List[Dict[str, Any]] = Field(default_factory=list)
    classification: str  # S, I, R, etc.
    rule_version: str
    profile_pack: str
    user_id: Optional[str] = None
    client_ip: Optional[str] = None
    timestamp: Optional[datetime] = None
    success: bool = True
    error_message: Optional[str] = None
    additional_metadata: Dict[str, Any] = Field(default_factory=dict)


class FHIRAuditEventBuilder:
    """Builder class for creating FHIR R4 AuditEvent resources from AMR classifications."""
    
    def __init__(self, service_name: str = "amr-engine", service_version: str = "1.0.0"):
        self.service_name = service_name
        self.service_version = service_version
    
    def build_from_classification(self, result: ClassificationResult) -> FHIRAuditEvent:
        """
        Build FHIR R4 AuditEvent from AMR classification result.
        
        Args:
            result: Classification result data
            
        Returns:
            Complete FHIR R4 AuditEvent resource
        """
        event_id = str(uuid.uuid4())
        timestamp = result.timestamp or datetime.now(timezone.utc)
        
        # Determine outcome based on success/failure
        outcome = AuditEventOutcome.SUCCESS if result.success else AuditEventOutcome.SERIOUS_FAILURE
        
        # Build type and subtype
        event_type = FHIRCoding(
            system="http://terminology.hl7.org/CodeSystem/audit-event-type",
            code="110112",
            display="Query"
        )
        
        subtypes = [
            FHIRCoding(
                system="http://terminology.hl7.org/CodeSystem/iso-21089-lifecycle",
                code="access",
                display="Access/View"
            ),
            FHIRCoding(
                system="http://hl7.org/fhir/restful-interaction",
                code="create", 
                display="create"
            )
        ]
        
        # Build agents
        agents = self._build_agents(result)
        
        # Build source
        source = self._build_source()
        
        # Build entities
        entities = self._build_entities(result)
        
        # Build meta information
        meta = {
            "versionId": "1",
            "lastUpdated": timestamp.isoformat(),
            "profile": ["http://hl7.org/fhir/StructureDefinition/AuditEvent"],
            "tag": [
                {
                    "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
                    "code": "HTEST",
                    "display": "test health data"
                }
            ]
        }
        
        return FHIRAuditEvent(
            id=event_id,
            meta=meta,
            type=event_type,
            subtype=subtypes,
            action=AuditEventAction.CREATE,
            recorded=timestamp.isoformat(),
            outcome=outcome,
            outcomeDesc=result.error_message if not result.success else f"AMR classification completed: {result.classification}",
            agent=agents,
            source=source,
            entity=entities
        )
    
    def _build_agents(self, result: ClassificationResult) -> List[FHIRAuditEventAgent]:
        """Build agent components for the audit event."""
        agents = []
        
        # System agent (AMR engine)
        system_agent = FHIRAuditEventAgent(
            type=FHIRCoding(
                system="http://terminology.hl7.org/CodeSystem/v3-ParticipationType",
                code="RESP",
                display="responsible party"
            ),
            who=FHIRReference(
                reference=f"Device/{self.service_name}",
                display=f"AMR Classification Engine v{self.service_version}"
            ),
            name=self.service_name,
            requestor=False,
            policy=[f"urn:ietf:rfc:3986#{self.service_name}-policy"]
        )
        agents.append(system_agent)
        
        # User agent (if user_id provided)
        if result.user_id:
            user_agent = FHIRAuditEventAgent(
                type=FHIRCoding(
                    system="http://terminology.hl7.org/CodeSystem/v3-ParticipationType",
                    code="IRCP",
                    display="information recipient"
                ),
                who=FHIRReference(
                    reference=f"Practitioner/{result.user_id}",
                    display=f"User {result.user_id}"
                ),
                name=result.user_id,
                requestor=True,
                network={
                    "address": result.client_ip,
                    "type": "2"  # IP Address
                } if result.client_ip else None
            )
            agents.append(user_agent)
        
        return agents
    
    def _build_source(self) -> FHIRAuditEventSource:
        """Build source component for the audit event."""
        return FHIRAuditEventSource(
            site="AMR-Laboratory",
            observer=FHIRReference(
                reference=f"Device/{self.service_name}",
                display="AMR Classification Engine"
            ),
            type=[
                FHIRCoding(
                    system="http://terminology.hl7.org/CodeSystem/security-source-type",
                    code="4",
                    display="Application Server"
                )
            ]
        )
    
    def _build_entities(self, result: ClassificationResult) -> List[FHIRAuditEventEntity]:
        """Build entity components for the audit event."""
        entities = []
        
        # Patient entity (if patient_id provided)
        if result.patient_id:
            patient_entity = FHIRAuditEventEntity(
                what=FHIRReference(
                    reference=f"Patient/{result.patient_id}",
                    display=f"Patient {result.patient_id}"
                ),
                type=FHIRCoding(
                    system="http://terminology.hl7.org/CodeSystem/audit-entity-type",
                    code="1",
                    display="Person"
                ),
                role=FHIRCoding(
                    system="http://terminology.hl7.org/CodeSystem/object-role",
                    code="1",
                    display="Patient"
                ),
                lifecycle=FHIRCoding(
                    system="http://terminology.hl7.org/CodeSystem/dicom-audit-lifecycle",
                    code="6",
                    display="Access/Use"
                ),
                name=f"Patient {result.patient_id}"
            )
            entities.append(patient_entity)
        
        # Specimen entity (if specimen_id provided)
        if result.specimen_id:
            specimen_entity = FHIRAuditEventEntity(
                what=FHIRReference(
                    reference=f"Specimen/{result.specimen_id}",
                    display=f"Specimen {result.specimen_id}"
                ),
                type=FHIRCoding(
                    system="http://terminology.hl7.org/CodeSystem/audit-entity-type",
                    code="2",
                    display="System Object"
                ),
                role=FHIRCoding(
                    system="http://terminology.hl7.org/CodeSystem/object-role",
                    code="3",
                    display="Report"
                ),
                lifecycle=FHIRCoding(
                    system="http://terminology.hl7.org/CodeSystem/dicom-audit-lifecycle",
                    code="6",
                    display="Access/Use"
                ),
                name=f"Laboratory Specimen {result.specimen_id}",
                description=f"Antimicrobial susceptibility test specimen for {result.organism or 'unknown organism'}"
            )
            entities.append(specimen_entity)
        
        # Classification observation entity
        observation_entity = FHIRAuditEventEntity(
            what=FHIRReference(
                reference=f"Observation/{result.correlation_id}",
                display=f"AMR Classification {result.correlation_id}"
            ),
            type=FHIRCoding(
                system="http://terminology.hl7.org/CodeSystem/audit-entity-type",
                code="2",
                display="System Object"
            ),
            role=FHIRCoding(
                system="http://terminology.hl7.org/CodeSystem/object-role",
                code="4",
                display="Domain Resource"
            ),
            lifecycle=FHIRCoding(
                system="http://terminology.hl7.org/CodeSystem/dicom-audit-lifecycle",
                code="1",
                display="Origination/Creation"
            ),
            name="AMR Classification Result",
            description=f"Antimicrobial resistance classification: {result.classification}",
            detail=[
                {
                    "type": "correlation_id",
                    "valueString": result.correlation_id
                },
                {
                    "type": "rule_version", 
                    "valueString": result.rule_version
                },
                {
                    "type": "profile_pack",
                    "valueString": result.profile_pack
                },
                {
                    "type": "organism",
                    "valueString": result.organism
                } if result.organism else {},
                {
                    "type": "classification_result",
                    "valueString": result.classification
                },
                {
                    "type": "antibiotics_tested",
                    "valueString": str(len(result.antibiotics))
                }
            ]
        )
        entities.append(observation_entity)
        
        return entities
    
    def to_json(self, audit_event: FHIRAuditEvent) -> str:
        """Convert FHIR AuditEvent to JSON string."""
        return audit_event.model_dump_json(exclude_none=True, by_alias=True)
    
    def to_dict(self, audit_event: FHIRAuditEvent) -> Dict[str, Any]:
        """Convert FHIR AuditEvent to dictionary."""
        return audit_event.model_dump(exclude_none=True, by_alias=True)