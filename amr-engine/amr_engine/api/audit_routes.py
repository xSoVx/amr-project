"""
API routes for audit event management and monitoring.

Provides endpoints for testing audit functionality, viewing metrics,
and managing the audit publisher service.
"""

from __future__ import annotations

import logging
from typing import Dict, Any, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request, status, Query, Depends
from pydantic import BaseModel, Field

from ..config import get_settings
from ..streaming.audit_publisher import (
    get_audit_publisher, 
    publish_classification_audit,
    ClassificationResult
)
from ..streaming.fhir_audit_event import FHIRAuditEventBuilder


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/audit", tags=["audit"])


class AuditTestRequest(BaseModel):
    """Request model for testing audit functionality."""
    
    correlation_id: str = Field(..., description="Classification correlation ID")
    patient_id: Optional[str] = Field(None, description="Patient identifier")
    specimen_id: Optional[str] = Field(None, description="Specimen identifier") 
    organism: Optional[str] = Field(None, description="Organism name")
    classification: str = Field("S", description="Classification result (S/I/R)")
    rule_version: str = Field("EUCAST_v2025.1", description="Rules version")
    profile_pack: str = Field("Base", description="FHIR profile pack used")
    user_id: Optional[str] = Field(None, description="User performing classification")
    client_ip: Optional[str] = Field(None, description="Client IP address")
    success: bool = Field(True, description="Whether classification succeeded")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    environment: str = Field("dev", description="Target environment (dev/staging/prod)")


class AuditStatusResponse(BaseModel):
    """Response model for audit service status."""
    
    enabled: bool
    environment: str
    publisher_status: Dict[str, Any]
    health_check: Dict[str, Any]


@router.get(
    "/status",
    response_model=AuditStatusResponse,
    summary="Get audit service status",
    description="Get current status of audit service including metrics and health"
)
async def get_audit_status() -> AuditStatusResponse:
    """Get audit service status and metrics."""
    settings = get_settings()
    
    if not settings.KAFKA_ENABLED:
        return AuditStatusResponse(
            enabled=False,
            environment="disabled",
            publisher_status={"status": "disabled"},
            health_check={"status": "disabled"}
        )
    
    try:
        async with get_audit_publisher(settings.KAFKA_ENVIRONMENT) as publisher:
            status = await publisher.get_status()
            health = await publisher.health_check()
            
            return AuditStatusResponse(
                enabled=True,
                environment=settings.KAFKA_ENVIRONMENT,
                publisher_status=status,
                health_check=health
            )
    
    except Exception as e:
        logger.error(f"Failed to get audit status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get audit status: {str(e)}"
        )


@router.post(
    "/test",
    summary="Test audit event publishing", 
    description="Send a test audit event to verify functionality"
)
async def test_audit_event(request: AuditTestRequest) -> Dict[str, Any]:
    """Send test audit event."""
    settings = get_settings()
    
    if not settings.KAFKA_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Audit publishing is disabled"
        )
    
    try:
        # Build test antibiotics data
        antibiotics = [
            {
                "name": "Ampicillin",
                "mic_value": "8",
                "interpretation": request.classification
            },
            {
                "name": "Ciprofloxacin", 
                "mic_value": "0.25",
                "interpretation": "S"
            }
        ] if request.organism else []
        
        # Publish audit event
        success = await publish_classification_audit(
            correlation_id=request.correlation_id,
            classification=request.classification,
            rule_version=request.rule_version,
            profile_pack=request.profile_pack,
            patient_id=request.patient_id,
            specimen_id=request.specimen_id,
            organism=request.organism,
            antibiotics=antibiotics,
            user_id=request.user_id,
            client_ip=request.client_ip,
            success=request.success,
            error_message=request.error_message,
            environment=request.environment
        )
        
        return {
            "success": success,
            "message": "Test audit event queued successfully" if success else "Failed to queue test audit event",
            "correlation_id": request.correlation_id,
            "environment": request.environment,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to send test audit event: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send test audit event: {str(e)}"
        )


@router.get(
    "/metrics",
    summary="Get audit metrics",
    description="Get detailed metrics about audit event processing"
)
async def get_audit_metrics(environment: str = Query("dev")) -> Dict[str, Any]:
    """Get audit service metrics."""
    settings = get_settings()
    
    if not settings.KAFKA_ENABLED:
        return {
            "enabled": False,
            "message": "Audit publishing is disabled"
        }
    
    try:
        async with get_audit_publisher(environment) as publisher:
            status = await publisher.get_status()
            return {
                "enabled": True,
                "environment": environment,
                "metrics": status.get("metrics", {}),
                "buffer_status": {
                    "size": status.get("buffer_size", 0),
                    "dropped": status.get("buffer_dropped", 0),
                    "max_size": publisher.buffer.max_size
                },
                "circuit_breaker": status.get("circuit_breaker", {}),
                "producer_metrics": status.get("producer_metrics", {})
            }
    
    except Exception as e:
        logger.error(f"Failed to get audit metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get audit metrics: {str(e)}"
        )


@router.post(
    "/flush",
    summary="Force flush buffer",
    description="Force immediate flush of all buffered audit events"
)
async def force_flush_buffer(environment: str = Query("dev")) -> Dict[str, Any]:
    """Force flush of audit event buffer."""
    settings = get_settings()
    
    if not settings.KAFKA_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Audit publishing is disabled"
        )
    
    try:
        async with get_audit_publisher(environment) as publisher:
            buffer_size_before = await publisher.buffer.size()
            await publisher.force_flush()
            buffer_size_after = await publisher.buffer.size()
            
            return {
                "success": True,
                "message": "Buffer flushed successfully",
                "events_flushed": buffer_size_before - buffer_size_after,
                "remaining_buffer_size": buffer_size_after,
                "timestamp": datetime.utcnow().isoformat()
            }
    
    except Exception as e:
        logger.error(f"Failed to flush buffer: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to flush buffer: {str(e)}"
        )


@router.get(
    "/health",
    summary="Audit service health check",
    description="Check health of audit service components"
)
async def audit_health_check(environment: str = Query("dev")) -> Dict[str, Any]:
    """Health check for audit service."""
    settings = get_settings()
    
    if not settings.KAFKA_ENABLED:
        return {
            "status": "disabled",
            "enabled": False,
            "message": "Audit publishing is disabled"
        }
    
    try:
        async with get_audit_publisher(environment) as publisher:
            health = await publisher.health_check()
            
            return {
                "enabled": True,
                "environment": environment,
                **health
            }
    
    except Exception as e:
        logger.error(f"Audit health check failed: {e}")
        return {
            "status": "unhealthy",
            "enabled": True,
            "environment": environment,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


@router.get(
    "/preview",
    summary="Preview FHIR AuditEvent",
    description="Generate and preview FHIR R4 AuditEvent JSON without publishing"
)
async def preview_audit_event(
    correlation_id: str = Query(...),
    patient_id: Optional[str] = Query(None),
    specimen_id: Optional[str] = Query(None),
    organism: Optional[str] = Query(None),
    classification: str = Query("S"),
    rule_version: str = Query("EUCAST_v2025.1"),
    profile_pack: str = Query("Base"),
    user_id: Optional[str] = Query(None)
) -> Dict[str, Any]:
    """Preview FHIR AuditEvent JSON without publishing."""
    try:
        # Create classification result
        result = ClassificationResult(
            correlation_id=correlation_id,
            patient_id=patient_id,
            specimen_id=specimen_id,
            organism=organism,
            antibiotics=[
                {
                    "name": "Ampicillin",
                    "mic_value": "8", 
                    "interpretation": classification
                }
            ] if organism else [],
            classification=classification,
            rule_version=rule_version,
            profile_pack=profile_pack,
            user_id=user_id,
            success=True
        )
        
        # Build FHIR AuditEvent
        builder = FHIRAuditEventBuilder()
        audit_event = builder.build_from_classification(result)
        
        # Convert to dictionary
        fhir_json = builder.to_dict(audit_event)
        
        return {
            "fhir_audit_event": fhir_json,
            "preview_note": "This is a preview - no event was published",
            "resource_type": audit_event.resourceType,
            "audit_event_id": audit_event.id,
            "timestamp": audit_event.recorded
        }
        
    except Exception as e:
        logger.error(f"Failed to preview audit event: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to preview audit event: {str(e)}"
        )


@router.get(
    "/topics",
    summary="Get topic mapping",
    description="Get Kafka topic names for different environments"
)
async def get_topic_mapping() -> Dict[str, Any]:
    """Get Kafka topic mapping for different environments."""
    topic_mapping = {
        "dev": "amr-audit-dev",
        "development": "amr-audit-dev", 
        "staging": "amr-audit-staging",
        "stage": "amr-audit-staging",
        "production": "amr-audit-prod",
        "prod": "amr-audit-prod"
    }
    
    settings = get_settings()
    current_env = settings.KAFKA_ENVIRONMENT
    current_topic = topic_mapping.get(current_env.lower(), "amr-audit-dev")
    
    return {
        "current_environment": current_env,
        "current_topic": current_topic,
        "topic_mapping": topic_mapping,
        "dlq_suffix": "-dlq",
        "kafka_enabled": settings.KAFKA_ENABLED
    }