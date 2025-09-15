"""
Audit integration service for classification endpoints.

Provides seamless audit event publishing for all classification operations
without blocking the main response flow.
"""

from __future__ import annotations

import logging
import asyncio
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from contextlib import asynccontextmanager

from prometheus_client import Counter, Histogram, Gauge
from fastapi import BackgroundTasks, Request

from ..config import get_settings
from ..core.correlation import get_or_create_correlation_id, extract_correlation_id_from_request
from ..core.schemas import ClassificationResult

logger = logging.getLogger(__name__)

# Audit metrics
audit_events_total = Counter(
    'audit_events_total', 
    'Total audit events processed',
    ['status', 'environment']
)

audit_publish_duration = Histogram(
    'audit_publish_duration_seconds',
    'Time spent publishing audit events',
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0]
)

audit_buffer_size = Gauge(
    'audit_buffer_size',
    'Current size of audit event buffer',
    ['environment']
)

audit_failed_events = Counter(
    'audit_failed_events_total',
    'Total failed audit events',
    ['environment', 'error_type']
)


class AuditIntegrationService:
    """Service for integrating audit publishing with classification endpoints."""
    
    def __init__(self):
        self.settings = get_settings()
        self._publisher = None
        self._initialized = False
    
    @property
    def is_enabled(self) -> bool:
        """Check if audit publishing is enabled."""
        return (
            self.settings.KAFKA_ENABLED and 
            hasattr(self.settings, 'AUDIT_STREAMING_ENABLED') and
            getattr(self.settings, 'AUDIT_STREAMING_ENABLED', True)
        )
    
    async def initialize(self) -> None:
        """Initialize the audit publisher if needed."""
        if not self.is_enabled or self._initialized:
            return
            
        try:
            # Import here to avoid circular imports and handle missing dependencies
            from ..streaming.audit_publisher import get_audit_publisher
            self._publisher = await get_audit_publisher(self.settings.KAFKA_ENVIRONMENT).__aenter__()
            self._initialized = True
            logger.info("Audit integration service initialized successfully")
        except ImportError:
            logger.warning("Audit publisher not available - audit streaming disabled")
        except Exception as e:
            logger.error(f"Failed to initialize audit publisher: {e}")
            audit_failed_events.labels(
                environment=self.settings.KAFKA_ENVIRONMENT,
                error_type="initialization_error"
            ).inc()
    
    async def shutdown(self) -> None:
        """Gracefully shutdown audit publisher."""
        if self._publisher:
            try:
                # Force flush any pending events
                await self._publisher.force_flush()
                await self._publisher.__aexit__(None, None, None)
                logger.info("Audit publisher shutdown completed")
            except Exception as e:
                logger.error(f"Error during audit publisher shutdown: {e}")
    
    async def publish_classification_audit(
        self,
        classification_results: List[ClassificationResult],
        request: Request,
        correlation_id: Optional[str] = None,
        user_id: Optional[str] = None,
        additional_metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Publish audit events for classification results."""
        if not self.is_enabled or not self._initialized:
            return False
        
        # Ensure correlation ID is available
        if not correlation_id:
            correlation_id = get_or_create_correlation_id()
        
        # Extract user info from request
        client_ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        
        try:
            with audit_publish_duration.time():
                # Publish audit event for each classification result
                success_count = 0
                for result in classification_results:
                    try:
                        # Import here to handle missing dependencies
                        from ..streaming.audit_publisher import publish_classification_audit
                        
                        # Prepare antibiotics data from classification result
                        antibiotics = []
                        if result.antibiotic and result.decision:
                            antibiotics.append({
                                "name": result.antibiotic,
                                "mic_value": str(result.input.get("mic_mg_L", "")) if result.input.get("mic_mg_L") else None,
                                "disc_zone_mm": str(result.input.get("disc_zone_mm", "")) if result.input.get("disc_zone_mm") else None,
                                "interpretation": result.decision
                            })
                        
                        # Publish audit event
                        success = await publish_classification_audit(
                            correlation_id=correlation_id,
                            classification=result.decision,
                            rule_version=result.ruleVersion or "Unknown",
                            profile_pack="Base",  # Default profile pack
                            patient_id=result.input.get("patientId"),
                            specimen_id=result.specimenId,
                            organism=result.organism,
                            antibiotics=antibiotics,
                            user_id=user_id,
                            client_ip=client_ip,
                            success=True,
                            environment=self.settings.KAFKA_ENVIRONMENT,
                            additional_metadata={
                                "user_agent": user_agent,
                                "endpoint": str(request.url.path),
                                "method": request.method,
                                **(additional_metadata or {})
                            }
                        )
                        
                        if success:
                            success_count += 1
                            audit_events_total.labels(
                                status="success",
                                environment=self.settings.KAFKA_ENVIRONMENT
                            ).inc()
                        else:
                            audit_events_total.labels(
                                status="failed",
                                environment=self.settings.KAFKA_ENVIRONMENT
                            ).inc()
                            audit_failed_events.labels(
                                environment=self.settings.KAFKA_ENVIRONMENT,
                                error_type="publish_failed"
                            ).inc()
                            
                    except Exception as e:
                        logger.error(f"Failed to publish audit event for result: {e}")
                        audit_events_total.labels(
                            status="error",
                            environment=self.settings.KAFKA_ENVIRONMENT
                        ).inc()
                        audit_failed_events.labels(
                            environment=self.settings.KAFKA_ENVIRONMENT,
                            error_type="publish_error"
                        ).inc()
                
                logger.debug(f"Published {success_count}/{len(classification_results)} audit events successfully")
                return success_count > 0
                
        except Exception as e:
            logger.error(f"Failed to publish audit events: {e}")
            audit_failed_events.labels(
                environment=self.settings.KAFKA_ENVIRONMENT,
                error_type="service_error"
            ).inc()
            return False
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get health status of audit integration."""
        if not self.is_enabled:
            return {
                "status": "disabled",
                "enabled": False,
                "reason": "Audit streaming is disabled"
            }
        
        if not self._initialized:
            return {
                "status": "not_initialized",
                "enabled": True,
                "reason": "Audit publisher not yet initialized"
            }
        
        try:
            if self._publisher:
                # Get publisher health status
                health = await self._publisher.health_check()
                return {
                    "status": "healthy" if health.get("status") == "healthy" else "unhealthy",
                    "enabled": True,
                    "publisher_health": health
                }
            else:
                return {
                    "status": "unhealthy", 
                    "enabled": True,
                    "reason": "Publisher not available"
                }
        except Exception as e:
            return {
                "status": "unhealthy",
                "enabled": True, 
                "error": str(e)
            }


# Global audit integration service instance
_audit_service: Optional[AuditIntegrationService] = None


def get_audit_service() -> AuditIntegrationService:
    """Get or create the global audit integration service."""
    global _audit_service
    if not _audit_service:
        _audit_service = AuditIntegrationService()
    return _audit_service


async def publish_classification_audit_background(
    classification_results: List[ClassificationResult],
    request: Request,
    correlation_id: Optional[str] = None,
    user_id: Optional[str] = None,
    additional_metadata: Optional[Dict[str, Any]] = None
) -> None:
    """Background task for publishing classification audit events."""
    audit_service = get_audit_service()
    try:
        await audit_service.publish_classification_audit(
            classification_results=classification_results,
            request=request,
            correlation_id=correlation_id,
            user_id=user_id,
            additional_metadata=additional_metadata
        )
    except Exception as e:
        logger.error(f"Background audit publishing failed: {e}")


def add_audit_background_task(
    background_tasks: BackgroundTasks,
    classification_results: List[ClassificationResult],
    request: Request,
    correlation_id: Optional[str] = None,
    user_id: Optional[str] = None,
    additional_metadata: Optional[Dict[str, Any]] = None
) -> None:
    """Add audit publishing as a background task."""
    background_tasks.add_task(
        publish_classification_audit_background,
        classification_results,
        request,
        correlation_id,
        user_id,
        additional_metadata
    )


@asynccontextmanager
async def audit_service_lifespan():
    """Context manager for audit service lifecycle."""
    audit_service = get_audit_service()
    try:
        await audit_service.initialize()
        yield audit_service
    finally:
        await audit_service.shutdown()