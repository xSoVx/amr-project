"""
Enhanced domain-specific metrics for AMR Classification Engine.

Implements comprehensive metrics as recommended in the AMR Unified System
documentation for monitoring classification coverage, terminology mapping,
and system performance.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Any, Dict, Generator, Optional

from prometheus_client import Counter, Histogram, Gauge, Info, CollectorRegistry


class AMRMetrics:
    """
    Domain-specific metrics collector for AMR Classification Engine.
    
    Tracks:
    - Classification operations and outcomes
    - Terminology mapping coverage
    - Profile pack validation
    - Rule engine performance
    - Error rates by category
    """
    
    def __init__(self, registry: Optional[CollectorRegistry] = None):
        self.registry = registry or CollectorRegistry()
        
        # Classification metrics
        self.classifications_total = Counter(
            "amr_classifications_total",
            "Total AMR classifications performed",
            labelnames=["decision", "organism", "antibiotic", "method", "rule_version"],
            registry=self.registry
        )
        
        self.classification_duration = Histogram(
            "amr_classification_duration_seconds",
            "Time spent on classification operations",
            labelnames=["organism", "method"],
            buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
            registry=self.registry
        )
        
        self.rule_coverage = Counter(
            "amr_rule_coverage_total",
            "Number of times each rule was applied",
            labelnames=["rule_id", "organism", "antibiotic"],
            registry=self.registry
        )
        
        # Terminology mapping metrics
        self.terminology_lookups = Counter(
            "amr_terminology_lookups_total", 
            "Terminology lookup attempts",
            labelnames=["code_system", "status"],
            registry=self.registry
        )
        
        self.terminology_miss_rate = Gauge(
            "amr_terminology_miss_rate",
            "Percentage of unmapped terms by code system",
            labelnames=["code_system"],
            registry=self.registry
        )
        
        self.terminology_cache_hits = Counter(
            "amr_terminology_cache_hits_total",
            "Terminology cache hits",
            labelnames=["code_system"],
            registry=self.registry
        )
        
        # Profile pack validation metrics  
        self.profile_validations = Counter(
            "amr_profile_validations_total",
            "FHIR profile validation attempts",
            labelnames=["profile_pack", "pack_version", "result"],
            registry=self.registry
        )
        
        self.profile_selection = Counter(
            "amr_profile_selections_total",
            "Profile pack selections",
            labelnames=["profile_pack", "selection_source", "tenant_id"],
            registry=self.registry
        )
        
        self.validation_failures_by_binding = Counter(
            "amr_validation_failures_by_binding_total",
            "Validation failures by binding type and strength",
            labelnames=["profile_pack", "binding_type", "binding_strength"],
            registry=self.registry
        )
        
        # Ingestion metrics
        self.ingestion_messages = Counter(
            "amr_ingestion_messages_total",
            "Messages processed by ingestion service",
            labelnames=["format", "status"],
            registry=self.registry
        )
        
        self.hl7_segment_errors = Counter(
            "amr_hl7_segment_errors_total",
            "HL7v2 segment parsing errors",
            labelnames=["segment_type", "error_type"],
            registry=self.registry
        )
        
        self.fhir_resource_processing = Counter(
            "amr_fhir_resource_processing_total",
            "FHIR resource processing attempts",
            labelnames=["resource_type", "status"],
            registry=self.registry
        )
        
        # Error taxonomy metrics
        self.structured_errors = Counter(
            "amr_structured_errors_total",
            "Structured errors by category and code",
            labelnames=["category", "error_code", "severity"],
            registry=self.registry
        )
        
        # System performance metrics
        self.queue_depth = Gauge(
            "amr_queue_depth",
            "Current depth of processing queues",
            labelnames=["queue_name"],
            registry=self.registry
        )
        
        self.active_connections = Gauge(
            "amr_active_connections",
            "Number of active connections by type",
            labelnames=["connection_type"],
            registry=self.registry
        )
        
        # Audit metrics
        self.audit_events = Counter(
            "amr_audit_events_total",
            "FHIR AuditEvent generation",
            labelnames=["event_type", "outcome"],
            registry=self.registry
        )
        
        # Rule engine specific metrics
        self.rule_evaluation_time = Histogram(
            "amr_rule_evaluation_seconds",
            "Time spent evaluating classification rules",
            labelnames=["rule_type"],
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5],
            registry=self.registry
        )
        
        self.ml_model_inference = Histogram(
            "amr_ml_inference_seconds", 
            "ML model inference time",
            labelnames=["model_name", "batch_size"],
            buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0],
            registry=self.registry
        )
        
        # Service info
        self.service_info = Info(
            "amr_service_info",
            "AMR service information",
            registry=self.registry
        )
    
    def record_classification(
        self,
        decision: str,
        organism: Optional[str] = None,
        antibiotic: Optional[str] = None, 
        method: Optional[str] = None,
        rule_version: Optional[str] = None,
        duration: Optional[float] = None
    ):
        """Record a completed classification."""
        labels = {
            "decision": decision,
            "organism": organism or "unknown",
            "antibiotic": antibiotic or "unknown",
            "method": method or "unknown", 
            "rule_version": rule_version or "unknown"
        }
        
        self.classifications_total.labels(**labels).inc()
        
        if duration and organism and method:
            self.classification_duration.labels(
                organism=organism,
                method=method
            ).observe(duration)
    
    def record_rule_usage(
        self,
        rule_id: str,
        organism: str,
        antibiotic: str
    ):
        """Record usage of a specific rule."""
        self.rule_coverage.labels(
            rule_id=rule_id,
            organism=organism, 
            antibiotic=antibiotic
        ).inc()
    
    def record_terminology_lookup(
        self,
        code_system: str,
        found: bool,
        cache_hit: bool = False
    ):
        """Record terminology lookup result."""
        status = "found" if found else "not_found"
        self.terminology_lookups.labels(
            code_system=code_system,
            status=status
        ).inc()
        
        if cache_hit:
            self.terminology_cache_hits.labels(
                code_system=code_system
            ).inc()
    
    def update_terminology_miss_rate(
        self,
        code_system: str,
        miss_rate_percent: float
    ):
        """Update terminology miss rate gauge."""
        self.terminology_miss_rate.labels(
            code_system=code_system
        ).set(miss_rate_percent)
    
    def record_profile_validation(
        self,
        profile_pack: str,
        pack_version: str,
        success: bool,
        binding_failures: Optional[Dict[str, int]] = None
    ):
        """Record FHIR profile validation result."""
        result = "success" if success else "failure"
        self.profile_validations.labels(
            profile_pack=profile_pack,
            pack_version=pack_version,
            result=result
        ).inc()
        
        if binding_failures:
            for binding_type, count in binding_failures.items():
                # Extract binding strength from type if available
                parts = binding_type.split(":")
                binding_name = parts[0] 
                binding_strength = parts[1] if len(parts) > 1 else "unknown"
                
                self.validation_failures_by_binding.labels(
                    profile_pack=profile_pack,
                    binding_type=binding_name,
                    binding_strength=binding_strength
                )._value._value += count  # Add count rather than increment by 1
    
    def record_profile_selection(
        self,
        profile_pack: str,
        selection_source: str,
        tenant_id: Optional[str] = None
    ):
        """Record profile pack selection event."""
        self.profile_selection.labels(
            profile_pack=profile_pack,
            selection_source=selection_source,
            tenant_id=tenant_id or "unknown"
        ).inc()
    
    def record_ingestion_message(
        self,
        format_type: str,
        success: bool
    ):
        """Record message ingestion attempt.""" 
        status = "success" if success else "failure"
        self.ingestion_messages.labels(
            format=format_type,
            status=status
        ).inc()
    
    def record_hl7_segment_error(
        self,
        segment_type: str,
        error_type: str
    ):
        """Record HL7v2 segment parsing error."""
        self.hl7_segment_errors.labels(
            segment_type=segment_type,
            error_type=error_type  
        ).inc()
    
    def record_fhir_resource_processing(
        self,
        resource_type: str,
        success: bool
    ):
        """Record FHIR resource processing attempt."""
        status = "success" if success else "failure"
        self.fhir_resource_processing.labels(
            resource_type=resource_type,
            status=status
        ).inc()
    
    def record_structured_error(
        self,
        category: str,
        error_code: str,
        severity: str
    ):
        """Record structured error occurrence."""
        self.structured_errors.labels(
            category=category,
            error_code=error_code,
            severity=severity
        ).inc()
    
    def set_queue_depth(
        self,
        queue_name: str,
        depth: int
    ):
        """Update queue depth gauge."""
        self.queue_depth.labels(queue_name=queue_name).set(depth)
    
    def set_active_connections(
        self,
        connection_type: str,
        count: int
    ):
        """Update active connections gauge."""
        self.active_connections.labels(connection_type=connection_type).set(count)
    
    def record_audit_event(
        self,
        event_type: str,
        outcome: str
    ):
        """Record FHIR AuditEvent generation."""
        self.audit_events.labels(
            event_type=event_type,
            outcome=outcome
        ).inc()
    
    @contextmanager  
    def time_rule_evaluation(self, rule_type: str) -> Generator[None, None, None]:
        """Context manager to time rule evaluation."""
        start_time = time.time()
        try:
            yield
        finally:
            duration = time.time() - start_time
            self.rule_evaluation_time.labels(rule_type=rule_type).observe(duration)
    
    @contextmanager
    def time_ml_inference(self, model_name: str, batch_size: int = 1) -> Generator[None, None, None]:
        """Context manager to time ML model inference."""
        start_time = time.time()
        try:
            yield
        finally:
            duration = time.time() - start_time
            self.ml_model_inference.labels(
                model_name=model_name,
                batch_size=str(batch_size)
            ).observe(duration)
    
    def set_service_info(self, **info_labels: str):
        """Set service information labels."""
        self.service_info.info(info_labels)
    
    @contextmanager
    def time_classification(self, organism: str, method: str) -> Generator[float, None, None]:
        """Context manager to time classification operations."""
        start_time = time.time()
        try:
            yield start_time
        finally:
            duration = time.time() - start_time
            self.classification_duration.labels(
                organism=organism,
                method=method
            ).observe(duration)


# Global metrics instance
metrics = AMRMetrics()