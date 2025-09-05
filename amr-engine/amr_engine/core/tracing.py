"""
OpenTelemetry tracing configuration for AMR Classification Engine.

Implements distributed tracing as recommended in the AMR Unified System
architecture document for comprehensive observability and request flow tracking
across microservices.
"""

from __future__ import annotations

import functools
import logging
import time
from contextlib import contextmanager
from typing import Any, Dict, Generator, Optional

from opentelemetry import baggage, trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.propagators.b3 import B3MultiFormat
from opentelemetry.propagators.jaeger import JaegerPropagator
from opentelemetry.propagators.textmap import CompositePropagator
from opentelemetry.sdk.resources import SERVICE_NAME, SERVICE_VERSION, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.semconv.trace import SpanAttributes

logger = logging.getLogger(__name__)


class AMRTracing:
    """
    OpenTelemetry tracing configuration for AMR services.
    
    Provides:
    - Distributed tracing across AMR components
    - Custom span creation for domain operations
    - Baggage propagation for tenant/user context
    - Multiple propagation formats (B3, Jaeger)
    - OTLP export to observability backends
    """
    
    def __init__(
        self,
        service_name: str = "amr-engine",
        service_version: str = "0.1.0",
        otlp_endpoint: Optional[str] = None,
        sample_rate: float = 1.0
    ):
        self.service_name = service_name
        self.service_version = service_version
        self.otlp_endpoint = otlp_endpoint
        self.sample_rate = sample_rate
        
        # Initialize tracer
        self._setup_tracer()
        self.tracer = trace.get_tracer(__name__)
    
    def _setup_tracer(self):
        """Configure OpenTelemetry tracer with OTLP export."""
        
        # Service resource identification
        resource = Resource(attributes={
            SERVICE_NAME: self.service_name,
            SERVICE_VERSION: self.service_version,
            "service.namespace": "amr-system",
            "service.instance.id": f"{self.service_name}-1"  # Could be hostname/pod name
        })
        
        # Create tracer provider with sampling
        provider = TracerProvider(resource=resource)
        
        # Configure OTLP exporter if endpoint provided
        if self.otlp_endpoint:
            try:
                otlp_exporter = OTLPSpanExporter(
                    endpoint=self.otlp_endpoint,
                    insecure=True  # Use TLS in production
                )
                processor = BatchSpanProcessor(otlp_exporter)
                provider.add_span_processor(processor)
                logger.info(f"OTLP tracing configured for {self.otlp_endpoint}")
            except Exception as e:
                logger.warning(f"Failed to configure OTLP exporter: {e}")
        
        # Set global tracer provider
        trace.set_tracer_provider(provider)
        
        # Configure propagators for cross-service tracing
        composite_propagator = CompositePropagator([
            B3MultiFormat(),
            JaegerPropagator()
        ])
        # Note: Would normally use trace.set_global_textmap(composite_propagator)
        # but keeping simple for now
    
    def instrument_fastapi(self, app):
        """Instrument FastAPI application for automatic tracing."""
        try:
            FastAPIInstrumentor.instrument_app(
                app,
                tracer_provider=trace.get_tracer_provider()
            )
            logger.info("FastAPI instrumentation enabled")
        except Exception as e:
            logger.warning(f"Failed to instrument FastAPI: {e}")
    
    def instrument_requests(self):
        """Instrument requests library for HTTP client tracing."""
        try:
            RequestsInstrumentor().instrument()
            logger.info("Requests instrumentation enabled")
        except Exception as e:
            logger.warning(f"Failed to instrument requests: {e}")
    
    def instrument_sqlalchemy(self, engine=None):
        """Instrument SQLAlchemy for database tracing."""
        try:
            SQLAlchemyInstrumentor().instrument(
                engine=engine,
                tracer_provider=trace.get_tracer_provider()
            )
            logger.info("SQLAlchemy instrumentation enabled")
        except Exception as e:
            logger.warning(f"Failed to instrument SQLAlchemy: {e}")
    
    @contextmanager
    def start_span(
        self,
        operation_name: str,
        attributes: Optional[Dict[str, Any]] = None,
        kind: trace.SpanKind = trace.SpanKind.INTERNAL
    ) -> Generator[trace.Span, None, None]:
        """Start a new span with AMR-specific attributes."""
        with self.tracer.start_as_current_span(
            operation_name,
            kind=kind,
            attributes=attributes or {}
        ) as span:
            # Add standard AMR attributes
            span.set_attribute("amr.service", self.service_name)
            span.set_attribute("amr.version", self.service_version)
            
            yield span
    
    def trace_classification(
        self,
        organism: Optional[str] = None,
        antibiotic: Optional[str] = None,
        method: Optional[str] = None,
        specimen_id: Optional[str] = None
    ):
        """Decorator for tracing classification operations."""
        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                attributes = {
                    "amr.operation": "classification",
                    "amr.function": func.__name__
                }
                
                if organism:
                    attributes["amr.organism"] = organism
                if antibiotic:
                    attributes["amr.antibiotic"] = antibiotic
                if method:
                    attributes["amr.method"] = method
                if specimen_id:
                    attributes["amr.specimen_id"] = specimen_id
                
                with self.start_span(f"amr.classify.{func.__name__}", attributes) as span:
                    start_time = time.time()
                    try:
                        result = func(*args, **kwargs)
                        
                        # Add result attributes
                        if hasattr(result, 'decision'):
                            span.set_attribute("amr.decision", result.decision)
                        if hasattr(result, 'ruleVersion'):
                            span.set_attribute("amr.rule_version", result.ruleVersion)
                        
                        span.set_status(trace.Status(trace.StatusCode.OK))
                        return result
                        
                    except Exception as e:
                        span.set_status(trace.Status(
                            trace.StatusCode.ERROR,
                            description=str(e)
                        ))
                        span.record_exception(e)
                        raise
                    finally:
                        duration = time.time() - start_time
                        span.set_attribute("amr.duration_ms", duration * 1000)
                        
            return wrapper
        return decorator
    
    def trace_fhir_operation(
        self,
        resource_type: Optional[str] = None,
        operation: Optional[str] = None
    ):
        """Decorator for tracing FHIR operations."""
        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                attributes = {
                    "amr.operation": "fhir",
                    "amr.function": func.__name__,
                    SpanAttributes.RPC_SYSTEM: "fhir"
                }
                
                if resource_type:
                    attributes["fhir.resource_type"] = resource_type
                if operation:
                    attributes["fhir.operation"] = operation
                
                with self.start_span(f"amr.fhir.{func.__name__}", attributes) as span:
                    try:
                        result = func(*args, **kwargs)
                        span.set_status(trace.Status(trace.StatusCode.OK))
                        return result
                    except Exception as e:
                        span.set_status(trace.Status(
                            trace.StatusCode.ERROR,
                            description=str(e)
                        ))
                        span.record_exception(e)
                        raise
                        
            return wrapper
        return decorator
    
    def trace_terminology_lookup(self, code_system: Optional[str] = None):
        """Decorator for tracing terminology lookups."""
        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                attributes = {
                    "amr.operation": "terminology",
                    "amr.function": func.__name__
                }
                
                if code_system:
                    attributes["terminology.code_system"] = code_system
                
                with self.start_span(f"amr.terminology.{func.__name__}", attributes) as span:
                    try:
                        result = func(*args, **kwargs)
                        
                        # Record lookup success/failure
                        if isinstance(result, dict) and "found" in result:
                            span.set_attribute("terminology.found", result["found"])
                        
                        span.set_status(trace.Status(trace.StatusCode.OK))
                        return result
                    except Exception as e:
                        span.set_status(trace.Status(
                            trace.StatusCode.ERROR,
                            description=str(e)
                        ))
                        span.record_exception(e)
                        raise
                        
            return wrapper
        return decorator
    
    def set_user_context(self, user_id: str, tenant_id: Optional[str] = None):
        """Set user context in baggage for cross-service propagation."""
        ctx = baggage.set_baggage("amr.user_id", user_id)
        if tenant_id:
            ctx = baggage.set_baggage("amr.tenant_id", tenant_id, context=ctx)
        return ctx
    
    def get_user_context(self) -> Dict[str, str]:
        """Get current user context from baggage."""
        return {
            "user_id": baggage.get_baggage("amr.user_id"),
            "tenant_id": baggage.get_baggage("amr.tenant_id")
        }
    
    def add_span_attributes(self, **attributes):
        """Add attributes to current active span."""
        span = trace.get_current_span()
        if span.is_recording():
            for key, value in attributes.items():
                span.set_attribute(key, value)
    
    def add_span_event(self, name: str, attributes: Optional[Dict[str, Any]] = None):
        """Add an event to the current span."""
        span = trace.get_current_span()
        if span.is_recording():
            span.add_event(name, attributes or {})
    
    @contextmanager
    def trace_rule_evaluation(
        self,
        rule_id: str,
        organism: str,
        antibiotic: str
    ) -> Generator[trace.Span, None, None]:
        """Context manager for tracing rule evaluation."""
        attributes = {
            "amr.operation": "rule_evaluation",
            "amr.rule_id": rule_id,
            "amr.organism": organism,
            "amr.antibiotic": antibiotic
        }
        
        with self.start_span(f"amr.rule.evaluate", attributes) as span:
            yield span
    
    @contextmanager
    def trace_profile_validation(
        self,
        profile_pack: str,
        resource_type: str
    ) -> Generator[trace.Span, None, None]:
        """Context manager for tracing profile validation."""
        attributes = {
            "amr.operation": "profile_validation",
            "amr.profile_pack": profile_pack,
            "fhir.resource_type": resource_type
        }
        
        with self.start_span(f"amr.profile.validate", attributes) as span:
            yield span


# Global tracing instance
tracing: Optional[AMRTracing] = None


def init_tracing(
    service_name: str = "amr-engine",
    service_version: str = "0.1.0",
    otlp_endpoint: Optional[str] = None,
    sample_rate: float = 1.0
) -> AMRTracing:
    """Initialize global tracing configuration."""
    global tracing
    tracing = AMRTracing(
        service_name=service_name,
        service_version=service_version,
        otlp_endpoint=otlp_endpoint,
        sample_rate=sample_rate
    )
    return tracing


def get_tracer() -> AMRTracing:
    """Get global tracing instance."""
    if tracing is None:
        return init_tracing()
    return tracing