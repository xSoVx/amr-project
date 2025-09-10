"""
FHIR R4 AuditEvent generation for compliance and audit trails.

Implements FHIR AuditEvent resources as recommended in the AMR Unified System
architecture document for standardized audit logging and regulatory compliance.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from typing_extensions import Literal

try:
    from ..security.middleware import pseudonymize_patient_id
    PSEUDONYMIZATION_AVAILABLE = True
except ImportError:
    PSEUDONYMIZATION_AVAILABLE = False
    def pseudonymize_patient_id(patient_id: str, id_type: str = "Patient") -> str:
        return patient_id


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


class AuditSource(BaseModel):
    """FHIR AuditEvent.source."""
    site: Optional[str] = None
    identifier: str = Field(..., description="Audit source identifier")
    type: List[Dict[str, Any]] = Field(default_factory=list)


class AuditActor(BaseModel):
    """FHIR AuditEvent.agent."""
    type: Dict[str, Any] = Field(..., description="Agent type coding")
    who: Optional[Dict[str, str]] = None
    name: Optional[str] = None
    requestor: bool = False
    policy: List[str] = Field(default_factory=list)


class AuditEntity(BaseModel):
    """FHIR AuditEvent.entity."""
    what: Optional[Dict[str, str]] = None
    type: Optional[Dict[str, Any]] = None
    role: Optional[Dict[str, Any]] = None
    lifecycle: Optional[Dict[str, Any]] = None
    name: Optional[str] = None
    description: Optional[str] = None
    detail: List[Dict[str, Any]] = Field(default_factory=list)


class FHIRAuditEvent(BaseModel):
    """
    FHIR R4 AuditEvent resource for compliance logging.
    
    Tracks access, transforms, classification events, and rule version usage
    as recommended for AMR system auditability.
    """
    resourceType: Literal["AuditEvent"] = Field(default="AuditEvent")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    meta: Dict[str, Any] = Field(default_factory=dict)
    
    type: Dict[str, Any] = Field(..., description="Event type coding")
    subtype: List[Dict[str, Any]] = Field(default_factory=list)
    action: AuditEventAction
    period: Optional[Dict[str, str]] = None
    recorded: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    outcome: AuditEventOutcome = AuditEventOutcome.SUCCESS
    outcomeDesc: Optional[str] = None
    purposeOfEvent: List[Dict[str, Any]] = Field(default_factory=list)
    
    agent: List[AuditActor] = Field(..., description="Actors involved in the event")
    source: AuditSource = Field(..., description="Audit event source")
    entity: List[AuditEntity] = Field(default_factory=list)


class AMRAuditLogger:
    """
    AMR-specific audit event generator.
    
    Creates standardized FHIR AuditEvent resources for:
    - Classification operations
    - Rule version usage  
    - Profile pack selection
    - Data transformations
    - Access events
    """
    
    def __init__(self, service_name: str = "amr-engine"):
        self.service_name = service_name
        self.source = AuditSource(
            identifier=service_name,
            site="AMR Classification Engine",
            type=[{
                "system": "http://terminology.hl7.org/CodeSystem/security-source-type",
                "code": "4",
                "display": "Application Server"
            }]
        )
    
    def create_classification_event(
        self,
        specimen_id: str,
        organism: str,
        antibiotic: str,
        decision: str,
        rule_version: Optional[str] = None,
        user_id: Optional[str] = None,
        outcome: AuditEventOutcome = AuditEventOutcome.SUCCESS,
        outcome_desc: Optional[str] = None
    ) -> FHIRAuditEvent:
        """Create audit event for AMR classification operation with pseudonymized identifiers."""
        
        # Pseudonymize specimen ID for audit storage
        pseudonymized_specimen_id = pseudonymize_patient_id(specimen_id, "specimen_id")
        
        agents = [
            AuditActor(
                type={
                    "system": "http://terminology.hl7.org/CodeSystem/extra-security-role-type",
                    "code": "application",
                    "display": "Application"
                },
                name=self.service_name,
                requestor=True
            )
        ]
        
        if user_id:
            agents.append(AuditActor(
                type={
                    "system": "http://terminology.hl7.org/CodeSystem/v3-RoleCode", 
                    "code": "PROV",
                    "display": "Healthcare Provider"
                },
                who={"identifier": {"value": user_id}},
                requestor=False
            ))
        
        entities = [
            AuditEntity(
                what={"identifier": {"value": pseudonymized_specimen_id}},
                type={
                    "system": "http://terminology.hl7.org/CodeSystem/audit-entity-type",
                    "code": "2",
                    "display": "System Object"
                },
                role={
                    "system": "http://terminology.hl7.org/CodeSystem/object-role",
                    "code": "4", 
                    "display": "Domain Resource"
                },
                name=f"AMR Classification: {organism} vs {antibiotic}",
                detail=[
                    {
                        "type": "organism",
                        "valueString": organism
                    },
                    {
                        "type": "antibiotic", 
                        "valueString": antibiotic
                    },
                    {
                        "type": "decision",
                        "valueString": decision
                    },
                    {
                        "type": "pseudonymization_enabled",
                        "valueString": str(PSEUDONYMIZATION_AVAILABLE)
                    },
                    {
                        "type": "original_specimen_id_pseudonymized", 
                        "valueString": "true"
                    }
                ]
            )
        ]
        
        if rule_version:
            entities[0].detail.append({
                "type": "ruleVersion",
                "valueString": rule_version
            })
        
        return FHIRAuditEvent(
            type={
                "system": "http://terminology.hl7.org/CodeSystem/iso-21089-lifecycle",
                "code": "access-use",
                "display": "Access/Use"
            },
            subtype=[{
                "system": "http://hl7.org/fhir/restful-interaction", 
                "code": "create",
                "display": "Create"
            }],
            action=AuditEventAction.CREATE,
            outcome=outcome,
            outcomeDesc=outcome_desc,
            agent=agents,
            source=self.source,
            entity=entities
        )
    
    def create_profile_selection_event(
        self,
        profile_pack: str,
        pack_version: str,
        tenant_id: Optional[str] = None,
        override_source: Optional[str] = None,
        outcome: AuditEventOutcome = AuditEventOutcome.SUCCESS
    ) -> FHIRAuditEvent:
        """Create audit event for FHIR profile pack selection."""
        
        agents = [
            AuditActor(
                type={
                    "system": "http://terminology.hl7.org/CodeSystem/extra-security-role-type",
                    "code": "application", 
                    "display": "Application"
                },
                name=self.service_name,
                requestor=True
            )
        ]
        
        entities = [
            AuditEntity(
                what={"identifier": {"value": f"{profile_pack}@{pack_version}"}},
                type={
                    "system": "http://terminology.hl7.org/CodeSystem/audit-entity-type",
                    "code": "2",
                    "display": "System Object"
                },
                role={
                    "system": "http://terminology.hl7.org/CodeSystem/object-role",
                    "code": "5",
                    "display": "Master File"
                },
                name=f"Profile Pack Selection: {profile_pack}",
                detail=[
                    {
                        "type": "profilePack",
                        "valueString": profile_pack
                    },
                    {
                        "type": "packVersion", 
                        "valueString": pack_version
                    }
                ]
            )
        ]
        
        if tenant_id:
            entities[0].detail.append({
                "type": "tenantId",
                "valueString": tenant_id
            })
            
        if override_source:
            entities[0].detail.append({
                "type": "overrideSource",
                "valueString": override_source
            })
        
        return FHIRAuditEvent(
            type={
                "system": "http://terminology.hl7.org/CodeSystem/iso-21089-lifecycle",
                "code": "access-use", 
                "display": "Access/Use"
            },
            subtype=[{
                "system": "urn:amr:audit:subtype",
                "code": "profile-selection",
                "display": "Profile Pack Selection"
            }],
            action=AuditEventAction.READ,
            outcome=outcome,
            agent=agents,
            source=self.source,
            entity=entities
        )
    
    def create_rule_reload_event(
        self,
        rule_sources: List[str],
        user_id: str,
        outcome: AuditEventOutcome = AuditEventOutcome.SUCCESS,
        outcome_desc: Optional[str] = None
    ) -> FHIRAuditEvent:
        """Create audit event for rule reload operations."""
        
        agents = [
            AuditActor(
                type={
                    "system": "http://terminology.hl7.org/CodeSystem/v3-RoleCode",
                    "code": "ADMIN",
                    "display": "Administrator"
                },
                who={"identifier": {"value": user_id}},
                name="AMR Administrator",
                requestor=True
            )
        ]
        
        entities = []
        for i, source in enumerate(rule_sources):
            entities.append(AuditEntity(
                what={"identifier": {"value": source}},
                type={
                    "system": "http://terminology.hl7.org/CodeSystem/audit-entity-type",
                    "code": "2",
                    "display": "System Object"
                },
                role={
                    "system": "http://terminology.hl7.org/CodeSystem/object-role",
                    "code": "5",
                    "display": "Master File"
                },
                name=f"Rule Source {i+1}",
                detail=[{
                    "type": "ruleSource",
                    "valueString": source
                }]
            ))
        
        return FHIRAuditEvent(
            type={
                "system": "http://terminology.hl7.org/CodeSystem/iso-21089-lifecycle", 
                "code": "update",
                "display": "Update"
            },
            subtype=[{
                "system": "urn:amr:audit:subtype",
                "code": "rule-reload",
                "display": "Rule Configuration Reload"
            }],
            action=AuditEventAction.UPDATE,
            outcome=outcome,
            outcomeDesc=outcome_desc,
            agent=agents,
            source=self.source,
            entity=entities
        )
    
    def create_data_access_event(
        self,
        resource_type: str,
        resource_id: str,
        user_id: Optional[str] = None,
        action: AuditEventAction = AuditEventAction.READ,
        outcome: AuditEventOutcome = AuditEventOutcome.SUCCESS
    ) -> FHIRAuditEvent:
        """Create audit event for data access operations with pseudonymized identifiers."""
        
        # Pseudonymize resource ID based on resource type
        id_type = "Patient" if resource_type == "Patient" else "specimen_id"
        pseudonymized_resource_id = pseudonymize_patient_id(resource_id, id_type)
        
        agents = [
            AuditActor(
                type={
                    "system": "http://terminology.hl7.org/CodeSystem/extra-security-role-type",
                    "code": "application",
                    "display": "Application"
                },
                name=self.service_name,
                requestor=True
            )
        ]
        
        if user_id:
            agents.append(AuditActor(
                type={
                    "system": "http://terminology.hl7.org/CodeSystem/v3-RoleCode",
                    "code": "PROV", 
                    "display": "Healthcare Provider"
                },
                who={"identifier": {"value": user_id}},
                requestor=False
            ))
        
        return FHIRAuditEvent(
            type={
                "system": "http://terminology.hl7.org/CodeSystem/iso-21089-lifecycle",
                "code": "access-use",
                "display": "Access/Use"
            },
            action=action,
            outcome=outcome,
            agent=agents,
            source=self.source,
            entity=[
                AuditEntity(
                    what={"reference": f"{resource_type}/{pseudonymized_resource_id}"},
                    type={
                        "system": "http://terminology.hl7.org/CodeSystem/audit-entity-type",
                        "code": "2",
                        "display": "System Object"
                    },
                    role={
                        "system": "http://terminology.hl7.org/CodeSystem/object-role", 
                        "code": "4",
                        "display": "Domain Resource"
                    },
                    name=f"{resource_type} Resource Access",
                    detail=[
                        {
                            "type": "pseudonymization_enabled",
                            "valueString": str(PSEUDONYMIZATION_AVAILABLE)
                        },
                        {
                            "type": "original_resource_id_pseudonymized",
                            "valueString": "true"
                        }
                    ]
                )
            ]
        )