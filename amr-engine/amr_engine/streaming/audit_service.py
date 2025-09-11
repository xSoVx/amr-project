"""
Audit service integration for AMR engine.

Provides high-level interface for audit event streaming with
automatic producer lifecycle management and integration with
the AMR service.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any, List, AsyncContextManager
from datetime import datetime

from ..config import get_settings
from .audit_producer import AuditEventProducer, AuditEventMessage, RetryConfig
from .kafka_config import get_kafka_config_for_environment, KafkaEnvironment, KafkaSettings


logger = logging.getLogger(__name__)


class AuditService:
    """
    High-level audit service for AMR engine.
    
    Manages Kafka producer lifecycle and provides simplified
    interface for sending audit events.
    """
    
    def __init__(self, producer: Optional[AuditEventProducer] = None):
        self.producer = producer
        self._started = False
        
    @classmethod
    async def create(
        cls,
        kafka_environment: Optional[KafkaEnvironment] = None,
        retry_max_attempts: int = 3,
        retry_initial_delay: float = 1.0
    ) -> 'AuditService':
        """
        Create and start audit service.
        
        Args:
            kafka_environment: Environment configuration (local/staging/production)
            retry_max_attempts: Maximum retry attempts for failed sends
            retry_initial_delay: Initial delay for retries in seconds
        """
        settings = get_settings()
        
        if not settings.KAFKA_ENABLED:
            logger.info("Kafka disabled, creating null audit service")
            return cls(None)
        
        # Determine environment
        if kafka_environment is None:
            env_name = getattr(settings, 'KAFKA_ENVIRONMENT', 'local')
            kafka_environment = KafkaEnvironment(env_name)
        
        # Get configuration
        if hasattr(settings, 'KAFKA_BOOTSTRAP_SERVERS'):
            # Use settings-based configuration
            kafka_settings = KafkaSettings()
            config = kafka_settings.create_producer_config()
        else:
            # Use environment-based configuration
            config = get_kafka_config_for_environment(kafka_environment)
        
        # Create retry configuration
        retry_config = RetryConfig(
            max_retries=retry_max_attempts,
            initial_delay=retry_initial_delay
        )
        
        # Create and start producer
        producer = AuditEventProducer(config, retry_config)
        await producer.start()
        
        service = cls(producer)
        service._started = True
        return service
    
    async def close(self):
        """Close the audit service and stop producer."""
        if self.producer and self._started:
            await self.producer.stop()
            self._started = False
    
    async def send_classification_audit(
        self,
        classification_id: str,
        patient_id: Optional[str] = None,
        user_id: Optional[str] = None,
        client_ip: Optional[str] = None,
        organism: Optional[str] = None,
        antibiotics: Optional[List[str]] = None,
        outcome: str = "0",
        outcome_description: Optional[str] = None
    ) -> bool:
        """
        Send audit event for AMR classification.
        
        Args:
            classification_id: Unique ID for classification request
            patient_id: Patient identifier for partitioning
            user_id: User performing classification
            client_ip: Client IP address
            organism: Organism being classified
            antibiotics: List of antibiotics tested
            outcome: Audit outcome code (0=success, 4=minor failure, etc.)
            outcome_description: Optional description of outcome
            
        Returns:
            True if audit event was sent successfully
        """
        if not self.producer:
            logger.debug("Audit producer not available, skipping audit")
            return True
        
        try:
            # Build agent information
            agent = []
            if user_id:
                agent.append({
                    "type": {
                        "system": "http://terminology.hl7.org/CodeSystem/v3-ParticipationType",
                        "code": "IRCP",
                        "display": "Information Recipient"
                    },
                    "who": {
                        "reference": f"User/{user_id}",
                        "display": f"User {user_id}"
                    },
                    "requestor": True,
                    "network": {
                        "address": client_ip,
                        "type": "2"  # IP Address
                    } if client_ip else None
                })
            
            # Add system agent
            agent.append({
                "type": {
                    "system": "http://terminology.hl7.org/CodeSystem/v3-ParticipationType",
                    "code": "RESP",
                    "display": "Responsible Party"
                },
                "who": {
                    "reference": "Device/amr-engine",
                    "display": "AMR Classification Engine"
                },
                "requestor": False
            })
            
            # Build entity information
            entity = []
            if patient_id:
                entity.append({
                    "what": {
                        "reference": f"Patient/{patient_id}",
                        "display": f"Patient {patient_id}"
                    },
                    "type": {
                        "system": "http://terminology.hl7.org/CodeSystem/audit-entity-type",
                        "code": "1",
                        "display": "Person"
                    },
                    "role": {
                        "system": "http://terminology.hl7.org/CodeSystem/object-role",
                        "code": "1",
                        "display": "Patient"
                    }
                })
            
            # Add classification request entity
            entity.append({
                "what": {
                    "reference": f"Observation/{classification_id}",
                    "display": f"AMR Classification {classification_id}"
                },
                "type": {
                    "system": "http://terminology.hl7.org/CodeSystem/audit-entity-type",
                    "code": "2",
                    "display": "System Object"
                },
                "role": {
                    "system": "http://terminology.hl7.org/CodeSystem/object-role",
                    "code": "4",
                    "display": "Domain Resource"
                },
                "name": "AMR Classification Request",
                "description": f"Antimicrobial resistance classification for {organism or 'unknown organism'}"
            })
            
            # Build AMR context
            amr_context = {
                "classificationId": classification_id,
                "organism": organism,
                "antibiotics": antibiotics or [],
                "serviceVersion": "1.0.0"  # Could be pulled from settings
            }
            
            # Create audit message
            message = AuditEventMessage(
                type_system="http://terminology.hl7.org/CodeSystem/audit-event-type",
                type_code="rest",
                type_display="RESTful Operation",
                subtype=[
                    {
                        "system": "http://hl7.org/fhir/restful-interaction",
                        "code": "create",
                        "display": "Create"
                    },
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/iso-21089-lifecycle",
                        "code": "access",
                        "display": "Access/View"
                    }
                ],
                action="C",  # Create
                outcome=outcome,
                outcome_desc=outcome_description,
                agent=agent,
                source_site="amr-engine",
                entity=entity,
                patient_id=patient_id,
                amr_context=amr_context
            )
            
            return await self.producer.send_audit_event(message)
            
        except Exception as e:
            logger.error(f"Failed to send classification audit: {e}")
            return False
    
    async def send_access_audit(
        self,
        resource_type: str,
        resource_id: str,
        user_id: Optional[str] = None,
        client_ip: Optional[str] = None,
        outcome: str = "0"
    ) -> bool:
        """
        Send audit event for resource access.
        
        Args:
            resource_type: Type of FHIR resource accessed
            resource_id: ID of resource accessed
            user_id: User accessing resource
            client_ip: Client IP address
            outcome: Audit outcome code
            
        Returns:
            True if audit event was sent successfully
        """
        if not self.producer:
            return True
            
        try:
            agent = []
            if user_id:
                agent.append({
                    "who": {"reference": f"User/{user_id}"},
                    "requestor": True,
                    "network": {"address": client_ip, "type": "2"} if client_ip else None
                })
            
            entity = [{
                "what": {"reference": f"{resource_type}/{resource_id}"},
                "type": {
                    "system": "http://terminology.hl7.org/CodeSystem/audit-entity-type", 
                    "code": "2"
                }
            }]
            
            message = AuditEventMessage(
                type_code="rest",
                action="R",  # Read
                outcome=outcome,
                agent=agent,
                entity=entity
            )
            
            return await self.producer.send_audit_event(message)
            
        except Exception as e:
            logger.error(f"Failed to send access audit: {e}")
            return False
    
    async def send_error_audit(
        self,
        error_type: str,
        error_message: str,
        user_id: Optional[str] = None,
        client_ip: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Send audit event for errors.
        
        Args:
            error_type: Type of error
            error_message: Error message
            user_id: User associated with error
            client_ip: Client IP address
            context: Additional error context
            
        Returns:
            True if audit event was sent successfully
        """
        if not self.producer:
            return True
            
        try:
            agent = []
            if user_id:
                agent.append({
                    "who": {"reference": f"User/{user_id}"},
                    "requestor": True,
                    "network": {"address": client_ip, "type": "2"} if client_ip else None
                })
            
            message = AuditEventMessage(
                type_code="system",
                type_display="System Event",
                subtype=[{
                    "system": "http://terminology.hl7.org/CodeSystem/audit-event-sub-type",
                    "code": "error",
                    "display": "Error"
                }],
                action="E",  # Execute
                outcome="8",  # Serious failure
                outcome_desc=f"{error_type}: {error_message}",
                agent=agent,
                amr_context=context
            )
            
            return await self.producer.send_audit_event(message)
            
        except Exception as e:
            logger.error(f"Failed to send error audit: {e}")
            return False
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get audit service metrics."""
        if self.producer:
            return self.producer.get_metrics()
        return {"status": "disabled"}
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on audit service."""
        if not self.producer:
            return {"status": "disabled", "message": "Kafka audit disabled"}
        
        return await self.producer.health_check()


# Global audit service instance
_audit_service: Optional[AuditService] = None


@asynccontextmanager
async def get_audit_service() -> AsyncContextManager[AuditService]:
    """
    Get global audit service instance.
    
    Usage:
        async with get_audit_service() as audit:
            await audit.send_classification_audit(...)
    """
    global _audit_service
    
    if _audit_service is None:
        _audit_service = await AuditService.create()
    
    try:
        yield _audit_service
    finally:
        # Keep the service alive for reuse
        pass


async def initialize_audit_service() -> AuditService:
    """Initialize global audit service."""
    global _audit_service
    if _audit_service is None:
        _audit_service = await AuditService.create()
    return _audit_service


async def close_audit_service():
    """Close global audit service."""
    global _audit_service
    if _audit_service:
        await _audit_service.close()
        _audit_service = None


# Convenience functions for common audit events
async def audit_classification(
    classification_id: str,
    patient_id: Optional[str] = None,
    user_id: Optional[str] = None,
    client_ip: Optional[str] = None,
    organism: Optional[str] = None,
    antibiotics: Optional[List[str]] = None,
    success: bool = True
) -> bool:
    """Send classification audit event."""
    async with get_audit_service() as audit:
        return await audit.send_classification_audit(
            classification_id=classification_id,
            patient_id=patient_id,
            user_id=user_id,
            client_ip=client_ip,
            organism=organism,
            antibiotics=antibiotics,
            outcome="0" if success else "4"
        )


async def audit_access(
    resource_type: str,
    resource_id: str,
    user_id: Optional[str] = None,
    client_ip: Optional[str] = None
) -> bool:
    """Send access audit event."""
    async with get_audit_service() as audit:
        return await audit.send_access_audit(
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
            client_ip=client_ip
        )


async def audit_error(
    error_type: str,
    error_message: str,
    user_id: Optional[str] = None,
    client_ip: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None
) -> bool:
    """Send error audit event."""
    async with get_audit_service() as audit:
        return await audit.send_error_audit(
            error_type=error_type,
            error_message=error_message,
            user_id=user_id,
            client_ip=client_ip,
            context=context
        )