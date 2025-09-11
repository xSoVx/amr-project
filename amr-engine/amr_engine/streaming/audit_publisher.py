"""
AuditEvent publisher service with async fire-and-forget pattern, buffering,
circuit breaker for backpressure, and filesystem backup logging.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List, Deque
from collections import deque
from contextlib import asynccontextmanager
import aiofiles

from .fhir_audit_event import (
    FHIRAuditEventBuilder, 
    ClassificationResult, 
    FHIRAuditEvent
)
from .circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitBreakerOpenError
from .audit_producer import AuditEventProducer, create_audit_producer
from .kafka_config import KafkaProducerConfig, get_kafka_settings


logger = logging.getLogger(__name__)


class AuditEventBuffer:
    """Thread-safe buffer for audit events with size limits."""
    
    def __init__(self, max_size: int = 10000):
        self.max_size = max_size
        self.buffer: Deque[FHIRAuditEvent] = deque()
        self._lock = asyncio.Lock()
        self._dropped_count = 0
    
    async def add(self, event: FHIRAuditEvent) -> bool:
        """
        Add event to buffer.
        
        Returns:
            True if added successfully, False if buffer full
        """
        async with self._lock:
            if len(self.buffer) >= self.max_size:
                # Drop oldest event
                self.buffer.popleft()
                self._dropped_count += 1
                logger.warning(f"Buffer full, dropped oldest event. Total dropped: {self._dropped_count}")
            
            self.buffer.append(event)
            return True
    
    async def get_batch(self, batch_size: int = 100) -> List[FHIRAuditEvent]:
        """Get batch of events from buffer."""
        async with self._lock:
            batch = []
            for _ in range(min(batch_size, len(self.buffer))):
                if self.buffer:
                    batch.append(self.buffer.popleft())
            return batch
    
    async def size(self) -> int:
        """Get current buffer size."""
        async with self._lock:
            return len(self.buffer)
    
    async def clear(self) -> int:
        """Clear buffer and return number of cleared events."""
        async with self._lock:
            cleared = len(self.buffer)
            self.buffer.clear()
            return cleared
    
    @property
    def dropped_count(self) -> int:
        """Get number of dropped events."""
        return self._dropped_count


class FilesystemBackupLogger:
    """Filesystem backup logger for failed audit events."""
    
    def __init__(self, backup_dir: Path, max_file_size: int = 50 * 1024 * 1024):  # 50MB
        self.backup_dir = backup_dir
        self.max_file_size = max_file_size
        self.current_file: Optional[Path] = None
        self.current_size = 0
        
        # Create backup directory
        self.backup_dir.mkdir(parents=True, exist_ok=True)
    
    async def log_failure(
        self, 
        audit_event: FHIRAuditEvent, 
        error: Exception, 
        attempt_count: int = 1
    ):
        """Log failed audit event to filesystem."""
        try:
            if self.current_file is None or self.current_size >= self.max_file_size:
                await self._rotate_file()
            
            failure_record = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "audit_event_id": audit_event.id,
                "error": {
                    "type": type(error).__name__,
                    "message": str(error)
                },
                "attempt_count": attempt_count,
                "audit_event": json.loads(audit_event.model_dump_json(exclude_none=True))
            }
            
            record_json = json.dumps(failure_record, separators=(',', ':'))
            record_line = record_json + '\n'
            
            async with aiofiles.open(self.current_file, 'a', encoding='utf-8') as f:
                await f.write(record_line)
                self.current_size += len(record_line.encode('utf-8'))
            
            logger.info(f"Logged failed audit event {audit_event.id} to {self.current_file}")
            
        except Exception as backup_error:
            logger.error(f"Failed to log audit event to filesystem: {backup_error}")
    
    async def _rotate_file(self):
        """Rotate to new backup file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.current_file = self.backup_dir / f"audit_failures_{timestamp}_{uuid.uuid4().hex[:8]}.jsonl"
        self.current_size = 0
    
    async def get_backup_files(self) -> List[Path]:
        """Get list of backup files."""
        return list(self.backup_dir.glob("audit_failures_*.jsonl"))
    
    async def cleanup_old_files(self, keep_days: int = 30):
        """Clean up old backup files."""
        cutoff_time = datetime.now().timestamp() - (keep_days * 24 * 3600)
        
        for file_path in await self.get_backup_files():
            if file_path.stat().st_mtime < cutoff_time:
                try:
                    file_path.unlink()
                    logger.info(f"Cleaned up old backup file: {file_path}")
                except Exception as e:
                    logger.error(f"Failed to clean up {file_path}: {e}")


class AuditEventPublisher:
    """
    AuditEvent publisher with async fire-and-forget pattern, buffering,
    circuit breaker, and filesystem backup.
    """
    
    def __init__(
        self,
        environment: str = "dev",
        buffer_size: int = 10000,
        batch_size: int = 50,
        flush_interval: float = 5.0,
        backup_dir: Optional[Path] = None,
        circuit_breaker_config: Optional[CircuitBreakerConfig] = None
    ):
        self.environment = environment
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        
        # Components
        self.fhir_builder = FHIRAuditEventBuilder()
        self.buffer = AuditEventBuffer(buffer_size)
        self.producer: Optional[AuditEventProducer] = None
        
        # Circuit breaker for handling backpressure
        cb_config = circuit_breaker_config or CircuitBreakerConfig(
            failure_threshold=5,
            success_threshold=3,
            timeout=60.0
        )
        self.circuit_breaker = CircuitBreaker(cb_config)
        
        # Filesystem backup
        backup_path = backup_dir or Path("/tmp/amr-audit-backup")
        self.backup_logger = FilesystemBackupLogger(backup_path)
        
        # Background tasks
        self._flush_task: Optional[asyncio.Task] = None
        self._shutdown = False
        
        # Metrics
        self.metrics = {
            "events_published": 0,
            "events_buffered": 0,
            "events_failed": 0,
            "events_backed_up": 0,
            "circuit_breaker_trips": 0
        }
    
    async def start(self):
        """Start the audit event publisher."""
        try:
            # Create Kafka producer with environment-specific topic
            kafka_settings = get_kafka_settings()
            config = kafka_settings.create_producer_config()
            
            # Set environment-specific topic
            config.topic = self._get_topic_for_environment()
            config.dlq_topic = f"{config.topic}-dlq"
            
            self.producer = await create_audit_producer(config)
            
            # Start background flush task
            self._flush_task = asyncio.create_task(self._background_flush())
            
            logger.info(f"AuditEventPublisher started for environment: {self.environment}")
            
        except Exception as e:
            logger.error(f"Failed to start AuditEventPublisher: {e}")
            raise
    
    async def stop(self):
        """Stop the audit event publisher."""
        self._shutdown = True
        
        # Cancel background tasks
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        
        # Flush remaining events
        await self._flush_buffer()
        
        # Stop Kafka producer
        if self.producer:
            await self.producer.stop()
        
        logger.info("AuditEventPublisher stopped")
    
    def _get_topic_for_environment(self) -> str:
        """Get Kafka topic name for current environment."""
        topic_map = {
            "dev": "amr-audit-dev",
            "development": "amr-audit-dev",
            "staging": "amr-audit-staging",
            "stage": "amr-audit-staging", 
            "production": "amr-audit-prod",
            "prod": "amr-audit-prod"
        }
        return topic_map.get(self.environment.lower(), "amr-audit-dev")
    
    async def publish_classification(
        self,
        result: ClassificationResult
    ) -> bool:
        """
        Publish classification audit event (fire-and-forget).
        
        Args:
            result: Classification result to audit
            
        Returns:
            True if queued for publishing, False otherwise
        """
        try:
            # Build FHIR AuditEvent
            audit_event = self.fhir_builder.build_from_classification(result)
            
            # Add to buffer (fire-and-forget)
            await self.buffer.add(audit_event)
            self.metrics["events_buffered"] += 1
            
            logger.debug(f"Queued audit event for classification {result.correlation_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to queue audit event: {e}")
            self.metrics["events_failed"] += 1
            return False
    
    async def _background_flush(self):
        """Background task to flush buffer periodically."""
        while not self._shutdown:
            try:
                await asyncio.sleep(self.flush_interval)
                await self._flush_buffer()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in background flush: {e}")
    
    async def _flush_buffer(self):
        """Flush events from buffer to Kafka."""
        if not self.producer:
            return
        
        buffer_size = await self.buffer.size()
        if buffer_size == 0:
            return
        
        logger.debug(f"Flushing {buffer_size} events from buffer")
        
        # Process in batches
        while True:
            batch = await self.buffer.get_batch(self.batch_size)
            if not batch:
                break
            
            await self._publish_batch(batch)
    
    async def _publish_batch(self, batch: List[FHIRAuditEvent]):
        """Publish batch of audit events through circuit breaker."""
        for audit_event in batch:
            try:
                await self.circuit_breaker.call(
                    self._publish_single_event,
                    audit_event
                )
                self.metrics["events_published"] += 1
                
            except CircuitBreakerOpenError:
                # Circuit breaker is open, backup to filesystem
                await self.backup_logger.log_failure(
                    audit_event,
                    Exception("Circuit breaker open - Kafka unavailable")
                )
                self.metrics["events_backed_up"] += 1
                self.metrics["circuit_breaker_trips"] += 1
                
            except Exception as e:
                # Failed to publish, backup to filesystem
                await self.backup_logger.log_failure(audit_event, e)
                self.metrics["events_failed"] += 1
                self.metrics["events_backed_up"] += 1
    
    async def _publish_single_event(self, audit_event: FHIRAuditEvent):
        """Publish single audit event to Kafka."""
        if not self.producer:
            raise Exception("Producer not available")
        
        # Convert FHIR AuditEvent to our internal message format
        from .audit_producer import AuditEventMessage
        
        # Extract patient ID for partitioning
        patient_id = None
        for entity in audit_event.entity:
            if entity.what and entity.what.reference and entity.what.reference.startswith("Patient/"):
                patient_id = entity.what.reference.split("/")[-1]
                break
        
        # Create Kafka message
        kafka_message = AuditEventMessage(
            event_id=audit_event.id,
            recorded=datetime.fromisoformat(audit_event.recorded.replace('Z', '+00:00')),
            type_system=audit_event.type.system,
            type_code=audit_event.type.code,
            type_display=audit_event.type.display,
            subtype=[
                {
                    "system": st.system,
                    "code": st.code, 
                    "display": st.display
                }
                for st in audit_event.subtype
            ],
            action=audit_event.action.value if audit_event.action else "R",
            outcome=audit_event.outcome.value if audit_event.outcome else "0",
            outcome_desc=audit_event.outcomeDesc,
            patient_id=patient_id,
            # Add FHIR-specific context
            amr_context={
                "fhir_audit_event": json.loads(audit_event.model_dump_json(exclude_none=True)),
                "environment": self.environment
            }
        )
        
        success = await self.producer.send_audit_event(kafka_message)
        if not success:
            raise Exception("Failed to send audit event to Kafka")
    
    async def get_status(self) -> Dict[str, Any]:
        """Get publisher status and metrics."""
        buffer_size = await self.buffer.size()
        
        status = {
            "environment": self.environment,
            "topic": self._get_topic_for_environment(),
            "buffer_size": buffer_size,
            "buffer_dropped": self.buffer.dropped_count,
            "metrics": self.metrics.copy(),
            "circuit_breaker": self.circuit_breaker.get_status(),
            "producer_status": "available" if self.producer else "unavailable"
        }
        
        if self.producer:
            producer_metrics = self.producer.get_metrics()
            status["producer_metrics"] = producer_metrics
        
        return status
    
    async def force_flush(self):
        """Force flush of all buffered events."""
        await self._flush_buffer()
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check."""
        buffer_size = await self.buffer.size()
        
        health = {
            "status": "healthy",
            "buffer_size": buffer_size,
            "circuit_breaker_state": self.circuit_breaker.state.value,
            "producer_available": self.producer is not None
        }
        
        # Check if buffer is getting full
        if buffer_size > self.buffer.max_size * 0.8:
            health["status"] = "degraded"
            health["warning"] = "Buffer nearly full"
        
        # Check circuit breaker state
        if self.circuit_breaker.is_open:
            health["status"] = "degraded" 
            health["warning"] = "Circuit breaker open"
        
        # Check producer health
        if self.producer:
            producer_health = await self.producer.health_check()
            health["producer_health"] = producer_health
            if producer_health["status"] != "up":
                health["status"] = "degraded"
        
        return health


# Global publisher instance
_audit_publisher: Optional[AuditEventPublisher] = None


@asynccontextmanager
async def get_audit_publisher(environment: str = "dev"):
    """
    Get global audit publisher instance.
    
    Usage:
        async with get_audit_publisher("prod") as publisher:
            await publisher.publish_classification(result)
    """
    global _audit_publisher
    
    if _audit_publisher is None or _audit_publisher.environment != environment:
        if _audit_publisher:
            await _audit_publisher.stop()
        
        _audit_publisher = AuditEventPublisher(environment=environment)
        await _audit_publisher.start()
    
    try:
        yield _audit_publisher
    finally:
        # Keep publisher alive for reuse
        pass


async def initialize_audit_publisher(environment: str = "dev") -> AuditEventPublisher:
    """Initialize global audit publisher."""
    global _audit_publisher
    
    if _audit_publisher:
        await _audit_publisher.stop()
    
    _audit_publisher = AuditEventPublisher(environment=environment)
    await _audit_publisher.start()
    return _audit_publisher


async def close_audit_publisher():
    """Close global audit publisher."""
    global _audit_publisher
    if _audit_publisher:
        await _audit_publisher.stop()
        _audit_publisher = None


# Convenience functions
async def publish_classification_audit(
    correlation_id: str,
    classification: str,
    rule_version: str,
    profile_pack: str,
    patient_id: Optional[str] = None,
    specimen_id: Optional[str] = None,
    organism: Optional[str] = None,
    antibiotics: Optional[List[Dict[str, Any]]] = None,
    user_id: Optional[str] = None,
    client_ip: Optional[str] = None,
    success: bool = True,
    error_message: Optional[str] = None,
    environment: str = "dev"
) -> bool:
    """Convenience function to publish classification audit."""
    result = ClassificationResult(
        correlation_id=correlation_id,
        patient_id=patient_id,
        specimen_id=specimen_id,
        organism=organism,
        antibiotics=antibiotics or [],
        classification=classification,
        rule_version=rule_version,
        profile_pack=profile_pack,
        user_id=user_id,
        client_ip=client_ip,
        success=success,
        error_message=error_message
    )
    
    async with get_audit_publisher(environment) as publisher:
        return await publisher.publish_classification(result)