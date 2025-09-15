"""
Correlation ID middleware for FastAPI.

Automatically extracts or generates correlation IDs for all requests
and ensures they flow through the entire request lifecycle.
"""

from __future__ import annotations

import logging
from typing import Callable, Awaitable, Any

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from .correlation import extract_correlation_id_from_request, add_correlation_id_to_response_headers

logger = logging.getLogger(__name__)


class CorrelationIDMiddleware(BaseHTTPMiddleware):
    """Middleware to handle correlation ID extraction and injection."""
    
    def __init__(self, app: ASGIApp, header_name: str = "X-Correlation-ID"):
        super().__init__(app)
        self.header_name = header_name
    
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Extract or generate correlation ID from request
        correlation_id = extract_correlation_id_from_request(request)
        
        # Store correlation ID in request state for easy access
        request.state.correlation_id = correlation_id
        
        # Process the request
        response = await call_next(request)
        
        # Add correlation ID to response headers
        if correlation_id:
            response.headers[self.header_name] = correlation_id
        
        return response