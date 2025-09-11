"""
Kafka producer for FHIR AuditEvent streaming.

Provides async Kafka producer with retry logic, dead letter queue,
schema registry integration, and patient ID partitioning.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List, Union, Callable
import random
import math

import fastavro
from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaError, KafkaTimeoutError
# Schema registry imports (optional, fallback to direct Avro)
try:
    from confluent_kafka.schema_registry import SchemaRegistryClient
    from confluent_kafka.schema_registry.avro import AvroSerializer
    HAS_CONFLUENT_SCHEMA_REGISTRY = True
except ImportError:
    SchemaRegistryClient = None
    AvroSerializer = None
    HAS_CONFLUENT_SCHEMA_REGISTRY = False

from .kafka_config import KafkaProducerConfig, get_kafka_settings


logger = logging.getLogger(__name__)


class RetryConfig:
    """Configuration for retry logic with exponential backoff."""
    
    def __init__(
        self,
        max_retries: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        backoff_multiplier: float = 2.0,
        jitter: bool = True
    ):
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.backoff_multiplier = backoff_multiplier
        self.jitter = jitter
    
    def get_delay(self, attempt: int) -> float:
        """Calculate delay for given retry attempt."""
        delay = self.initial_delay * (self.backoff_multiplier ** attempt)
        delay = min(delay, self.max_delay)
        
        if self.jitter:
            # Add random jitter ±25%
            jitter_amount = delay * 0.25
            delay += random.uniform(-jitter_amount, jitter_amount)
        
        return max(0, delay)


class AuditEventMessage:
    """FHIR AuditEvent message for Kafka streaming."""
    
    def __init__(
        self,
        event_id: Optional[str] = None,
        recorded: Optional[datetime] = None,
        type_system: str = "http://terminology.hl7.org/CodeSystem/audit-event-type",
        type_code: str = "rest",
        type_display: Optional[str] = None,
        subtype: Optional[List[Dict[str, str]]] = None,
        action: str = "R",
        outcome: str = "0",
        outcome_desc: Optional[str] = None,
        agent: Optional[List[Dict[str, Any]]] = None,
        source_site: Optional[str] = None,
        source_observer: Optional[Dict[str, str]] = None,
        source_type: Optional[List[Dict[str, str]]] = None,
        entity: Optional[List[Dict[str, Any]]] = None,
        patient_id: Optional[str] = None,
        amr_context: Optional[Dict[str, Any]] = None
    ):
        self.id = event_id or str(uuid.uuid4())
        self.recorded = recorded or datetime.now(timezone.utc)
        self.type_system = type_system
        self.type_code = type_code
        self.type_display = type_display
        self.subtype = subtype or []
        self.action = action
        self.outcome = outcome
        self.outcome_desc = outcome_desc
        self.agent = agent or []
        self.source_site = source_site
        self.source_observer = source_observer or {
            "reference": "Device/amr-engine",
            "display": "AMR Classification Engine"
        }
        self.source_type = source_type or [
            {
                "system": "http://terminology.hl7.org/CodeSystem/security-source-type",
                "code": "4",
                "display": "Application Server"
            }
        ]
        self.entity = entity or []
        self.patient_id = patient_id
        self.amr_context = amr_context
    
    def to_avro_dict(self) -> Dict[str, Any]:
        """Convert to Avro-compatible dictionary."""
        return {
            "id": self.id,
            "resourceType": "AuditEvent",
            "recorded": int(self.recorded.timestamp() * 1000),  # Convert to milliseconds
            "type": {
                "system": self.type_system,
                "code": self.type_code,
                "display": self.type_display
            },
            "subtype": [
                {
                    "system": item.get("system", ""),
                    "code": item.get("code", ""),
                    "display": item.get("display")
                }
                for item in self.subtype
            ],
            "action": self.action,
            "outcome": self.outcome,
            "outcomeDesc": self.outcome_desc,
            "agent": [
                {
                    "type": agent.get("type"),
                    "role": agent.get("role", []),
                    "who": agent.get("who"),
                    "name": agent.get("name"),
                    "requestor": agent.get("requestor", False),
                    "network": agent.get("network")
                }
                for agent in self.agent
            ],
            "source": {
                "site": self.source_site,
                "observer": self.source_observer,
                "type": self.source_type
            },
            "entity": [
                {
                    "what": entity.get("what"),
                    "type": entity.get("type"),
                    "role": entity.get("role"),
                    "lifecycle": entity.get("lifecycle"),
                    "name": entity.get("name"),
                    "description": entity.get("description")
                }
                for entity in self.entity
            ],
            "patientId": self.patient_id,
            "amrContext": self.amr_context
        }
    
    def extract_patient_id(self) -> Optional[str]:
        """Extract patient ID from entities for partitioning."""
        if self.patient_id:
            return self.patient_id
            
        # Try to extract from entities
        for entity in self.entity:
            what = entity.get("what", {})
            if isinstance(what, dict):
                reference = what.get("reference", "")
                if reference.startswith("Patient/"):
                    return reference.split("/")[-1]
        
        return None


class DeadLetterQueue:
    """Dead letter queue for failed audit events."""
    
    def __init__(self, producer: AIOKafkaProducer, dlq_topic: str):
        self.producer = producer
        self.dlq_topic = dlq_topic
        self.failed_count = 0
    
    async def send_to_dlq(
        self,
        message: AuditEventMessage,
        error: Exception,
        original_topic: str,
        partition: Optional[int] = None
    ):
        """Send failed message to dead letter queue."""
        try:
            dlq_payload = {
                "original_topic": original_topic,
                "original_partition": partition,
                "error": str(error),
                "error_type": type(error).__name__,
                "timestamp": int(time.time() * 1000),
                "retry_count": getattr(message, "_retry_count", 0),
                "message": message.to_avro_dict()
            }
            
            # Use the same patient ID for partitioning in DLQ
            patient_id = message.extract_patient_id()
            key = patient_id.encode('utf-8') if patient_id else None
            
            await self.producer.send(
                topic=self.dlq_topic,
                value=json.dumps(dlq_payload).encode('utf-8'),
                key=key
            )
            
            self.failed_count += 1
            logger.error(
                f"Sent message to DLQ - Topic: {original_topic}, "
                f"Error: {error}, Patient: {patient_id}"
            )
            
        except Exception as dlq_error:
            logger.critical(f"Failed to send message to DLQ: {dlq_error}")


class AuditEventProducer:
    """Async Kafka producer for FHIR AuditEvents with retry and DLQ support."""
    
    def __init__(
        self,
        config: KafkaProducerConfig,
        retry_config: Optional[RetryConfig] = None,
        schema_path: Optional[Path] = None
    ):
        self.config = config
        self.retry_config = retry_config or RetryConfig()
        self.schema_path = schema_path or (Path(__file__).parent / "schemas" / "audit_event.avsc")
        
        self.producer: Optional[AIOKafkaProducer] = None
        self.dlq: Optional[DeadLetterQueue] = None
        self.avro_serializer: Optional[AvroSerializer] = None
        self.schema_registry_client: Optional[SchemaRegistryClient] = None
        
        # Metrics
        self.messages_sent = 0
        self.messages_failed = 0
        self.total_retries = 0
        
        # Load Avro schema
        self._load_schema()
    
    def _load_schema(self):
        """Load Avro schema from file."""
        try:
            with open(self.schema_path, 'r') as f:
                self.schema = fastavro.parse_schema(json.load(f))
            logger.info(f"Loaded Avro schema from {self.schema_path}")
        except Exception as e:
            logger.error(f"Failed to load Avro schema: {e}")
            self.schema = None
    
    def _setup_schema_registry(self):
        """Setup schema registry client and serializer."""
        if not self.config.schema_registry:
            logger.info("Schema registry not configured, using direct Avro serialization")
            return
        
        if not HAS_CONFLUENT_SCHEMA_REGISTRY:
            logger.warning("confluent-kafka not available, schema registry disabled")
            return
            
        try:
            # Create schema registry client
            sr_config = {
                'url': self.config.schema_registry.url
            }
            
            if self.config.schema_registry.username and self.config.schema_registry.password:
                sr_config.update({
                    'basic.auth.user.info': f"{self.config.schema_registry.username}:{self.config.schema_registry.password}"
                })
            
            # Add SSL config if provided
            if self.config.schema_registry.ssl_ca_cert_path:
                sr_config['ssl.ca.location'] = self.config.schema_registry.ssl_ca_cert_path
            if self.config.schema_registry.ssl_client_cert_path:
                sr_config['ssl.certificate.location'] = self.config.schema_registry.ssl_client_cert_path
            if self.config.schema_registry.ssl_client_key_path:
                sr_config['ssl.key.location'] = self.config.schema_registry.ssl_client_key_path
            
            self.schema_registry_client = SchemaRegistryClient(sr_config)
            
            # Create Avro serializer
            if self.schema:
                self.avro_serializer = AvroSerializer(
                    self.schema_registry_client,
                    json.dumps(self.schema)
                )
            
            logger.info("Schema registry client initialized")
            
        except Exception as e:
            logger.error(f"Failed to setup schema registry: {e}")
            self.schema_registry_client = None
            self.avro_serializer = None
    
    async def start(self):
        """Start the Kafka producer."""
        try:
            kafka_config = self.config.to_aiokafka_config()
            self.producer = AIOKafkaProducer(**kafka_config)
            
            await self.producer.start()
            self.dlq = DeadLetterQueue(self.producer, self.config.dlq_topic)
            
            # Setup schema registry
            self._setup_schema_registry()
            
            logger.info(f"Kafka producer started - Topic: {self.config.topic}")
            
        except Exception as e:
            logger.error(f"Failed to start Kafka producer: {e}")
            raise
    
    async def stop(self):
        """Stop the Kafka producer."""
        if self.producer:
            try:
                await self.producer.stop()
                logger.info("Kafka producer stopped")
            except Exception as e:
                logger.error(f"Error stopping producer: {e}")
    
    def _serialize_message(self, message: AuditEventMessage) -> bytes:
        """Serialize audit event message to Avro bytes."""
        avro_dict = message.to_avro_dict()
        
        if self.avro_serializer:
            # Use schema registry serializer
            return self.avro_serializer(avro_dict, None)
        elif self.schema:
            # Use direct fastavro serialization
            import io
            bytes_writer = io.BytesIO()
            fastavro.schemaless_writer(bytes_writer, self.schema, avro_dict)
            return bytes_writer.getvalue()
        else:
            # Fallback to JSON
            logger.warning("No schema available, falling back to JSON serialization")
            return json.dumps(avro_dict).encode('utf-8')
    
    def _get_partition_key(self, message: AuditEventMessage) -> Optional[bytes]:
        """Generate partition key from patient ID."""
        patient_id = message.extract_patient_id()
        return patient_id.encode('utf-8') if patient_id else None
    
    async def _send_with_retry(
        self,
        topic: str,
        message: AuditEventMessage,
        key: Optional[bytes] = None
    ) -> bool:
        """Send message with retry logic."""
        last_exception = None
        retry_count = 0
        
        for attempt in range(self.retry_config.max_retries + 1):
            try:
                serialized_message = self._serialize_message(message)
                
                # Send message
                record_metadata = await self.producer.send(
                    topic=topic,
                    value=serialized_message,
                    key=key
                )
                
                logger.debug(
                    f"Message sent successfully - Topic: {record_metadata.topic}, "
                    f"Partition: {record_metadata.partition}, "
                    f"Offset: {record_metadata.offset}, "
                    f"Patient: {message.extract_patient_id()}"
                )
                
                if retry_count > 0:
                    self.total_retries += retry_count
                    logger.info(f"Message sent after {retry_count} retries")
                
                self.messages_sent += 1
                return True
                
            except (KafkaError, KafkaTimeoutError) as e:
                last_exception = e
                retry_count += 1
                
                if attempt < self.retry_config.max_retries:
                    delay = self.retry_config.get_delay(attempt)
                    logger.warning(
                        f"Send failed (attempt {attempt + 1}/{self.retry_config.max_retries + 1}), "
                        f"retrying in {delay:.2f}s: {e}"
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Send failed after {self.retry_config.max_retries + 1} attempts: {e}")
                    break
            
            except Exception as e:
                logger.error(f"Unexpected error during send: {e}")
                last_exception = e
                break
        
        # Send to DLQ
        if self.dlq and last_exception:
            await self.dlq.send_to_dlq(message, last_exception, topic)
        
        self.messages_failed += 1
        return False
    
    async def send_audit_event(self, message: AuditEventMessage) -> bool:
        """
        Send audit event to Kafka topic.
        
        Args:
            message: AuditEvent message to send
            
        Returns:
            True if message was sent successfully, False otherwise
        """
        if not self.producer:
            logger.error("Producer not started")
            return False
        
        try:
            key = self._get_partition_key(message)
            return await self._send_with_retry(self.config.topic, message, key)
            
        except Exception as e:
            logger.error(f"Failed to send audit event: {e}")
            return False
    
    async def send_batch(self, messages: List[AuditEventMessage]) -> Dict[str, int]:
        """
        Send batch of audit events.
        
        Args:
            messages: List of audit event messages
            
        Returns:
            Dictionary with success/failure counts
        """
        results = {"success": 0, "failed": 0}
        
        # Create tasks for concurrent sending
        tasks = [
            self.send_audit_event(message)
            for message in messages
        ]
        
        # Wait for all tasks to complete
        task_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Count results
        for result in task_results:
            if isinstance(result, Exception):
                results["failed"] += 1
                logger.error(f"Batch send error: {result}")
            elif result:
                results["success"] += 1
            else:
                results["failed"] += 1
        
        logger.info(f"Batch send complete - Success: {results['success']}, Failed: {results['failed']}")
        return results
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get producer metrics."""
        return {
            "messages_sent": self.messages_sent,
            "messages_failed": self.messages_failed,
            "total_retries": self.total_retries,
            "dlq_messages": self.dlq.failed_count if self.dlq else 0,
            "success_rate": (
                self.messages_sent / (self.messages_sent + self.messages_failed)
                if (self.messages_sent + self.messages_failed) > 0
                else 0
            )
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on producer."""
        if not self.producer:
            return {"status": "down", "error": "Producer not started"}
        
        try:
            # Try to get cluster metadata as a health check
            cluster_metadata = self.producer.client.cluster
            
            return {
                "status": "up",
                "cluster_id": getattr(cluster_metadata, 'cluster_id', None),
                "brokers": len(cluster_metadata.brokers) if cluster_metadata else 0,
                "topic": self.config.topic,
                "metrics": self.get_metrics()
            }
        
        except Exception as e:
            return {
                "status": "degraded",
                "error": str(e),
                "metrics": self.get_metrics()
            }


# Factory function for easy instantiation
async def create_audit_producer(
    config: Optional[KafkaProducerConfig] = None,
    retry_config: Optional[RetryConfig] = None
) -> AuditEventProducer:
    """
    Create and start an audit event producer.
    
    Args:
        config: Kafka producer configuration (uses environment if not provided)
        retry_config: Retry configuration for failed sends
    
    Returns:
        Started AuditEventProducer instance
    """
    if not config:
        kafka_settings = get_kafka_settings()
        config = kafka_settings.create_producer_config()
    
    producer = AuditEventProducer(config, retry_config)
    await producer.start()
    return producer