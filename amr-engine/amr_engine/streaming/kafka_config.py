"""
Kafka configuration for different environments.

Provides environment-specific Kafka producer configurations with
authentication and SSL settings for local, staging, and production.
"""

from __future__ import annotations

import logging
import ssl
from pathlib import Path
from typing import Optional, Dict, Any, Literal
from enum import Enum

from pydantic import BaseModel, Field, validator
from pydantic_settings import BaseSettings


logger = logging.getLogger(__name__)


class KafkaEnvironment(str, Enum):
    """Kafka deployment environments."""
    LOCAL = "local"
    STAGING = "staging"
    PRODUCTION = "production"


class SecurityProtocol(str, Enum):
    """Kafka security protocols."""
    PLAINTEXT = "PLAINTEXT"
    SASL_PLAINTEXT = "SASL_PLAINTEXT"
    SASL_SSL = "SASL_SSL"
    SSL = "SSL"


class SaslMechanism(str, Enum):
    """SASL authentication mechanisms."""
    PLAIN = "PLAIN"
    SCRAM_SHA_256 = "SCRAM-SHA-256"
    SCRAM_SHA_512 = "SCRAM-SHA-512"
    GSSAPI = "GSSAPI"


class KafkaSSLConfig(BaseModel):
    """SSL configuration for Kafka connections."""
    
    ca_cert_path: Optional[str] = Field(None, description="Path to CA certificate file")
    client_cert_path: Optional[str] = Field(None, description="Path to client certificate file")
    client_key_path: Optional[str] = Field(None, description="Path to client private key file")
    cert_required: bool = Field(True, description="Whether to require certificate verification")
    check_hostname: bool = Field(True, description="Whether to check hostname in certificate")
    
    @validator('ca_cert_path', 'client_cert_path', 'client_key_path')
    def validate_cert_path(cls, v):
        if v and not Path(v).exists():
            logger.warning(f"Certificate file not found: {v}")
        return v


class KafkaSASLConfig(BaseModel):
    """SASL configuration for Kafka authentication."""
    
    mechanism: SaslMechanism = Field(SaslMechanism.PLAIN, description="SASL mechanism")
    username: Optional[str] = Field(None, description="SASL username")
    password: Optional[str] = Field(None, description="SASL password")
    
    @validator('username', 'password')
    def validate_sasl_credentials(cls, v, field):
        if field.name in ['username', 'password'] and not v:
            logger.warning(f"SASL {field.name} not provided")
        return v


class SchemaRegistryConfig(BaseModel):
    """Schema Registry configuration."""
    
    url: str = Field(..., description="Schema Registry URL")
    username: Optional[str] = Field(None, description="Schema Registry username")
    password: Optional[str] = Field(None, description="Schema Registry password")
    ssl_ca_cert_path: Optional[str] = Field(None, description="Path to CA cert for Schema Registry")
    ssl_client_cert_path: Optional[str] = Field(None, description="Path to client cert for Schema Registry")
    ssl_client_key_path: Optional[str] = Field(None, description="Path to client key for Schema Registry")


class KafkaProducerConfig(BaseModel):
    """Kafka producer configuration."""
    
    bootstrap_servers: str = Field(..., description="Kafka bootstrap servers")
    topic: str = Field("amr-audit-events", description="Kafka topic for audit events")
    dlq_topic: str = Field("amr-audit-events-dlq", description="Dead letter queue topic")
    
    security_protocol: SecurityProtocol = Field(
        SecurityProtocol.PLAINTEXT, 
        description="Security protocol for Kafka connection"
    )
    
    sasl_config: Optional[KafkaSASLConfig] = Field(None, description="SASL configuration")
    ssl_config: Optional[KafkaSSLConfig] = Field(None, description="SSL configuration")
    schema_registry: Optional[SchemaRegistryConfig] = Field(None, description="Schema Registry config")
    
    # Producer-specific settings
    acks: Literal["all", "0", "1"] = Field("all", description="Acknowledgment setting")
    retries: int = Field(5, description="Number of retries for failed sends")
    max_in_flight_requests_per_connection: int = Field(1, description="Max in-flight requests")
    enable_idempotence: bool = Field(True, description="Enable idempotent producer")
    compression_type: str = Field("snappy", description="Compression algorithm")
    batch_size: int = Field(16384, description="Batch size in bytes")
    linger_ms: int = Field(100, description="Time to wait for batching")
    buffer_memory: int = Field(33554432, description="Producer buffer memory")
    
    # Retry and timeout settings
    request_timeout_ms: int = Field(30000, description="Request timeout in milliseconds")
    retry_backoff_ms: int = Field(1000, description="Retry backoff in milliseconds")
    max_block_ms: int = Field(60000, description="Max time to block on send")
    
    def to_aiokafka_config(self) -> Dict[str, Any]:
        """Convert to aiokafka producer configuration."""
        config = {
            "bootstrap_servers": self.bootstrap_servers,
            "security_protocol": self.security_protocol.value,
            "acks": self.acks,
            "retries": self.retries,
            "max_in_flight_requests_per_connection": self.max_in_flight_requests_per_connection,
            "enable_idempotence": self.enable_idempotence,
            "compression_type": self.compression_type,
            "batch_size": self.batch_size,
            "linger_ms": self.linger_ms,
            "buffer_memory": self.buffer_memory,
            "request_timeout_ms": self.request_timeout_ms,
            "retry_backoff_ms": self.retry_backoff_ms,
            "max_block_ms": self.max_block_ms,
        }
        
        # Add SASL configuration
        if self.sasl_config:
            config.update({
                "sasl_mechanism": self.sasl_config.mechanism.value,
                "sasl_plain_username": self.sasl_config.username,
                "sasl_plain_password": self.sasl_config.password,
            })
        
        # Add SSL configuration
        if self.ssl_config:
            ssl_context = ssl.create_default_context()
            
            if self.ssl_config.ca_cert_path:
                ssl_context.load_verify_locations(self.ssl_config.ca_cert_path)
            
            if self.ssl_config.client_cert_path and self.ssl_config.client_key_path:
                ssl_context.load_cert_chain(
                    self.ssl_config.client_cert_path,
                    self.ssl_config.client_key_path
                )
            
            if not self.ssl_config.cert_required:
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
            elif not self.ssl_config.check_hostname:
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_REQUIRED
            
            config["ssl_context"] = ssl_context
        
        return config


class KafkaSettings(BaseSettings):
    """Kafka settings from environment variables."""
    
    # Environment
    KAFKA_ENVIRONMENT: KafkaEnvironment = Field(
        KafkaEnvironment.LOCAL,
        description="Kafka deployment environment"
    )
    
    # Connection
    KAFKA_BOOTSTRAP_SERVERS: str = Field(
        "localhost:9092",
        description="Kafka bootstrap servers"
    )
    
    # Topics
    KAFKA_AUDIT_TOPIC: str = Field(
        "amr-audit-events",
        description="Main audit events topic"
    )
    KAFKA_DLQ_TOPIC: str = Field(
        "amr-audit-events-dlq", 
        description="Dead letter queue topic"
    )
    
    # Security
    KAFKA_SECURITY_PROTOCOL: SecurityProtocol = Field(
        SecurityProtocol.PLAINTEXT,
        description="Kafka security protocol"
    )
    
    # SASL
    KAFKA_SASL_MECHANISM: Optional[SaslMechanism] = Field(
        None,
        description="SASL mechanism"
    )
    KAFKA_SASL_USERNAME: Optional[str] = Field(
        None,
        description="SASL username"
    )
    KAFKA_SASL_PASSWORD: Optional[str] = Field(
        None,
        description="SASL password"
    )
    
    # SSL/TLS
    KAFKA_SSL_CA_CERT_PATH: Optional[str] = Field(
        None,
        description="Path to SSL CA certificate"
    )
    KAFKA_SSL_CLIENT_CERT_PATH: Optional[str] = Field(
        None,
        description="Path to SSL client certificate"
    )
    KAFKA_SSL_CLIENT_KEY_PATH: Optional[str] = Field(
        None,
        description="Path to SSL client private key"
    )
    KAFKA_SSL_CERT_REQUIRED: bool = Field(
        True,
        description="Whether SSL certificate verification is required"
    )
    KAFKA_SSL_CHECK_HOSTNAME: bool = Field(
        True,
        description="Whether to verify SSL hostname"
    )
    
    # Schema Registry
    KAFKA_SCHEMA_REGISTRY_URL: Optional[str] = Field(
        None,
        description="Schema Registry URL"
    )
    KAFKA_SCHEMA_REGISTRY_USERNAME: Optional[str] = Field(
        None,
        description="Schema Registry username"
    )
    KAFKA_SCHEMA_REGISTRY_PASSWORD: Optional[str] = Field(
        None,
        description="Schema Registry password"
    )
    
    # Producer settings
    KAFKA_PRODUCER_ACKS: Literal["all", "0", "1"] = Field(
        "all",
        description="Producer acknowledgment setting"
    )
    KAFKA_PRODUCER_RETRIES: int = Field(
        5,
        description="Number of producer retries"
    )
    KAFKA_PRODUCER_BATCH_SIZE: int = Field(
        16384,
        description="Producer batch size"
    )
    KAFKA_PRODUCER_LINGER_MS: int = Field(
        100,
        description="Producer linger time"
    )
    
    class Config:
        env_prefix = ""
        case_sensitive = True

    def create_producer_config(self) -> KafkaProducerConfig:
        """Create producer configuration from settings."""
        
        # Create SASL config if needed
        sasl_config = None
        if self.KAFKA_SASL_MECHANISM:
            sasl_config = KafkaSASLConfig(
                mechanism=self.KAFKA_SASL_MECHANISM,
                username=self.KAFKA_SASL_USERNAME,
                password=self.KAFKA_SASL_PASSWORD
            )
        
        # Create SSL config if needed
        ssl_config = None
        if self.KAFKA_SECURITY_PROTOCOL in [SecurityProtocol.SSL, SecurityProtocol.SASL_SSL]:
            ssl_config = KafkaSSLConfig(
                ca_cert_path=self.KAFKA_SSL_CA_CERT_PATH,
                client_cert_path=self.KAFKA_SSL_CLIENT_CERT_PATH,
                client_key_path=self.KAFKA_SSL_CLIENT_KEY_PATH,
                cert_required=self.KAFKA_SSL_CERT_REQUIRED,
                check_hostname=self.KAFKA_SSL_CHECK_HOSTNAME
            )
        
        # Create Schema Registry config if URL provided
        schema_registry = None
        if self.KAFKA_SCHEMA_REGISTRY_URL:
            schema_registry = SchemaRegistryConfig(
                url=self.KAFKA_SCHEMA_REGISTRY_URL,
                username=self.KAFKA_SCHEMA_REGISTRY_USERNAME,
                password=self.KAFKA_SCHEMA_REGISTRY_PASSWORD
            )
        
        return KafkaProducerConfig(
            bootstrap_servers=self.KAFKA_BOOTSTRAP_SERVERS,
            topic=self.KAFKA_AUDIT_TOPIC,
            dlq_topic=self.KAFKA_DLQ_TOPIC,
            security_protocol=self.KAFKA_SECURITY_PROTOCOL,
            sasl_config=sasl_config,
            ssl_config=ssl_config,
            schema_registry=schema_registry,
            acks=self.KAFKA_PRODUCER_ACKS,
            retries=self.KAFKA_PRODUCER_RETRIES,
            batch_size=self.KAFKA_PRODUCER_BATCH_SIZE,
            linger_ms=self.KAFKA_PRODUCER_LINGER_MS
        )


def get_kafka_config_for_environment(env: KafkaEnvironment) -> KafkaProducerConfig:
    """Get pre-configured Kafka settings for specific environment."""
    
    if env == KafkaEnvironment.LOCAL:
        # Local development - no authentication
        return KafkaProducerConfig(
            bootstrap_servers="localhost:9092",
            topic="amr-audit-events",
            dlq_topic="amr-audit-events-dlq",
            security_protocol=SecurityProtocol.PLAINTEXT
        )
    
    elif env == KafkaEnvironment.STAGING:
        # Staging - SASL authentication
        return KafkaProducerConfig(
            bootstrap_servers="staging-kafka:9092",
            topic="staging-amr-audit-events",
            dlq_topic="staging-amr-audit-events-dlq",
            security_protocol=SecurityProtocol.SASL_SSL,
            sasl_config=KafkaSASLConfig(
                mechanism=SaslMechanism.SCRAM_SHA_256,
                username="${KAFKA_SASL_USERNAME}",
                password="${KAFKA_SASL_PASSWORD}"
            ),
            ssl_config=KafkaSSLConfig(
                ca_cert_path="/etc/ssl/certs/kafka-ca.pem"
            ),
            schema_registry=SchemaRegistryConfig(
                url="https://staging-schema-registry:8081"
            )
        )
    
    elif env == KafkaEnvironment.PRODUCTION:
        # Production - mTLS authentication
        return KafkaProducerConfig(
            bootstrap_servers="prod-kafka-cluster:9093",
            topic="prod-amr-audit-events", 
            dlq_topic="prod-amr-audit-events-dlq",
            security_protocol=SecurityProtocol.SSL,
            ssl_config=KafkaSSLConfig(
                ca_cert_path="/etc/ssl/certs/kafka-ca.pem",
                client_cert_path="/etc/ssl/certs/kafka-client.pem",
                client_key_path="/etc/ssl/private/kafka-client.key"
            ),
            schema_registry=SchemaRegistryConfig(
                url="https://prod-schema-registry:8081",
                ssl_ca_cert_path="/etc/ssl/certs/schema-registry-ca.pem",
                ssl_client_cert_path="/etc/ssl/certs/schema-registry-client.pem",
                ssl_client_key_path="/etc/ssl/private/schema-registry-client.key"
            ),
            acks="all",
            retries=10,
            enable_idempotence=True,
            max_in_flight_requests_per_connection=1
        )
    
    else:
        raise ValueError(f"Unsupported environment: {env}")


def get_kafka_settings() -> KafkaSettings:
    """Get Kafka settings from environment."""
    return KafkaSettings()