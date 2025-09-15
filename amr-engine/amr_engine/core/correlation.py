"""
Correlation ID management for request tracing.

Provides utilities for generating and managing correlation IDs
that flow through the entire request lifecycle.
"""

from __future__ import annotations

import uuid
import logging
from typing import Optional
from contextvars import ContextVar
from fastapi import Request

logger = logging.getLogger(__name__)

# Context variable to store correlation ID across async boundaries
correlation_id_context: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)


def generate_correlation_id() -> str:
    """Generate a new correlation ID."""
    return str(uuid.uuid4())


def get_correlation_id() -> Optional[str]:
    """Get the current correlation ID from context."""
    return correlation_id_context.get()


def set_correlation_id(correlation_id: str) -> None:
    """Set the correlation ID in the current context."""
    correlation_id_context.set(correlation_id)


def get_or_create_correlation_id() -> str:
    """Get existing correlation ID or create a new one."""
    correlation_id = get_correlation_id()
    if not correlation_id:
        correlation_id = generate_correlation_id()
        set_correlation_id(correlation_id)
    return correlation_id


def extract_correlation_id_from_request(request: Request) -> str:
    """Extract or generate correlation ID from HTTP request."""
    # Check for correlation ID in headers (multiple common header names)
    correlation_id = (
        request.headers.get("X-Correlation-ID") or
        request.headers.get("X-Request-ID") or
        request.headers.get("X-Trace-ID") or
        request.headers.get("Correlation-ID") or
        request.headers.get("Request-ID")
    )
    
    if not correlation_id:
        correlation_id = generate_correlation_id()
        logger.debug(f"Generated new correlation ID: {correlation_id}")
    else:
        logger.debug(f"Using correlation ID from request: {correlation_id}")
    
    set_correlation_id(correlation_id)
    return correlation_id


def add_correlation_id_to_response_headers(response_headers: dict, correlation_id: Optional[str] = None) -> dict:
    """Add correlation ID to response headers."""
    if not correlation_id:
        correlation_id = get_correlation_id()
    
    if correlation_id:
        response_headers["X-Correlation-ID"] = correlation_id
        
    return response_headers