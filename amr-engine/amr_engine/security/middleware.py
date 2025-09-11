"""
Patient Identifier Pseudonymization Middleware

FastAPI middleware that intercepts ALL requests and pseudonymizes patient identifiers
BEFORE external library processing. This ensures PHI protection at the entry point
of the application, preventing real patient data from being processed by downstream
components.
"""

import json
import logging
from typing import Any, Dict, Optional, Union
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse
import asyncio
from contextlib import asynccontextmanager

from .pseudonymization import PseudonymizationService, PseudonymizationConfig

logger = logging.getLogger(__name__)


class PseudonymizationMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for patient identifier pseudonymization.
    
    This middleware:
    1. Intercepts ALL incoming requests
    2. Detects request content type (FHIR, HL7v2, JSON)
    3. Pseudonymizes patient identifiers BEFORE external libraries process data
    4. Maintains consistent dummy IDs across requests
    5. Logs pseudonymization events for audit trails
    """
    
    def __init__(self, app, config: Optional[PseudonymizationConfig] = None):
        """
        Initialize pseudonymization middleware.
        
        Args:
            app: FastAPI application instance
            config: Pseudonymization configuration
        """
        super().__init__(app)
        self.config = config or PseudonymizationConfig()
        self.pseudonymization_service = PseudonymizationService(self.config)
        
        # Paths to exclude from pseudonymization
        self.excluded_paths = {
            "/health", "/healthz", "/ready", "/version", 
            "/docs", "/openapi.json", "/openapi.yaml", "/redoc",
            "/metrics", "/admin/rules/reload", "/classify/fhir"  # TEMPORARY: Skip FHIR for testing
        }
        
        # Content types that require pseudonymization
        self.pseudonymizable_content_types = {
            "application/json",
            "application/fhir+json", 
            "application/x-hl7-v2+er7",
            "text/plain"  # For HL7v2 messages
        }
        
        logger.info("PseudonymizationMiddleware initialized")
    
    async def dispatch(self, request: Request, call_next) -> StarletteResponse:
        """
        Process request through pseudonymization pipeline.
        
        Args:
            request: Incoming FastAPI request
            call_next: Next middleware/handler in chain
            
        Returns:
            Response from downstream handlers
        """
        # Skip pseudonymization for excluded paths
        if request.url.path in self.excluded_paths:
            return await call_next(request)
        
        # Skip GET requests (no request body to pseudonymize)
        if request.method == "GET":
            return await call_next(request)
        
        # Check if request has body and appropriate content type
        content_type = request.headers.get("content-type", "").lower()
        if not any(ct in content_type for ct in self.pseudonymizable_content_types):
            return await call_next(request)
        
        try:
            # Read and pseudonymize request body
            pseudonymized_request = await self._pseudonymize_request(request)
            
            # Process request with pseudonymized data
            response = await call_next(pseudonymized_request)
            
            # Log successful pseudonymization
            await self._log_pseudonymization_event(
                request, 
                success=True,
                message="Request successfully pseudonymized"
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Pseudonymization middleware error: {e}")
            
            # Log failed pseudonymization
            await self._log_pseudonymization_event(
                request,
                success=False, 
                message=f"Pseudonymization failed: {str(e)}"
            )
            
            # Return error response
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Pseudonymization error",
                    "detail": "Failed to process patient identifiers",
                    "type": "pseudonymization_error"
                }
            )
    
    async def _pseudonymize_request(self, request: Request) -> Request:
        """
        Pseudonymize patient identifiers in request body.
        
        Args:
            request: Original request
            
        Returns:
            Request with pseudonymized body
        """
        # Read request body
        body = await request.body()
        if not body:
            return request
        
        # Detect content type and pseudonymize accordingly
        content_type = request.headers.get("content-type", "").lower()
        
        try:
            if "hl7" in content_type or "x-application/hl7-v2+er7" in content_type:
                # Process HL7v2 message
                pseudonymized_body = await self._pseudonymize_hl7v2_body(body)
            
            elif "json" in content_type or "fhir" in content_type:
                # Process JSON/FHIR content
                pseudonymized_body = await self._pseudonymize_json_body(body, request)
            
            else:
                # Try to detect format from content
                body_text = body.decode('utf-8', errors='ignore')
                if body_text.strip().startswith('MSH|'):
                    # HL7v2 message auto-detected
                    pseudonymized_body = await self._pseudonymize_hl7v2_body(body)
                else:
                    # Assume JSON and try to parse
                    pseudonymized_body = await self._pseudonymize_json_body(body, request)
            
            # Create new request with pseudonymized body
            pseudonymized_request = await self._create_request_with_body(
                request, 
                pseudonymized_body
            )
            
            return pseudonymized_request
            
        except Exception as e:
            logger.error(f"Failed to pseudonymize request body: {e}")
            raise
    
    async def _pseudonymize_hl7v2_body(self, body: bytes) -> bytes:
        """
        Pseudonymize HL7v2 message body.
        
        Args:
            body: Raw HL7v2 message bytes
            
        Returns:
            Pseudonymized HL7v2 message bytes
        """
        try:
            hl7_message = body.decode('utf-8', errors='ignore')
            pseudonymized_message = self.pseudonymization_service.pseudonymize_hl7v2_message(hl7_message)
            if pseudonymized_message is None:
                logger.warning("Pseudonymized HL7v2 message is None, returning original body")
                return body
            return pseudonymized_message.encode('utf-8')
        except Exception as e:
            logger.error(f"Failed to pseudonymize HL7v2 body: {e}")
            raise
    
    async def _pseudonymize_json_body(self, body: bytes, request: Request) -> bytes:
        """
        Pseudonymize JSON/FHIR body.
        
        Args:
            body: Raw JSON body bytes
            request: Original request (for context)
            
        Returns:
            Pseudonymized JSON body bytes
        """
        try:
            # Parse JSON
            json_data = json.loads(body.decode('utf-8'))
            
            # Determine if this is FHIR content
            if self._is_fhir_content(json_data, request):
                # Use FHIR-specific pseudonymization
                pseudonymized_data = self.pseudonymization_service.pseudonymize_fhir_bundle(json_data)
            else:
                # Use generic JSON pseudonymization
                pseudonymized_data = self.pseudonymization_service.pseudonymize_json_data(json_data)
            
            # Convert back to JSON bytes
            if pseudonymized_data is None:
                logger.warning("Pseudonymized data is None, returning original body")
                return body
            return json.dumps(pseudonymized_data).encode('utf-8')
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON body: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to pseudonymize JSON body: {e}")
            raise
    
    def _is_fhir_content(self, json_data: Any, request: Request) -> bool:
        """
        Determine if JSON content is FHIR-based.
        
        Args:
            json_data: Parsed JSON data
            request: Original request
            
        Returns:
            True if content appears to be FHIR
        """
        # Check content type header
        content_type = request.headers.get("content-type", "").lower()
        if "fhir" in content_type:
            return True
        
        # Check URL path for FHIR endpoints
        if "/fhir" in request.url.path or "/classify/fhir" in request.url.path:
            return True
        
        # Check for FHIR-specific fields in JSON
        if isinstance(json_data, dict):
            # Single FHIR resource
            if "resourceType" in json_data:
                return True
            
            # FHIR Bundle
            if json_data.get("resourceType") == "Bundle" and "entry" in json_data:
                return True
                
            # Array of FHIR resources
            if isinstance(json_data, list) and len(json_data) > 0:
                if isinstance(json_data[0], dict) and "resourceType" in json_data[0]:
                    return True
        
        return False
    
    async def _create_request_with_body(self, original_request: Request, new_body: bytes) -> Request:
        """
        Create new request with modified body.
        
        Args:
            original_request: Original FastAPI request
            new_body: New request body bytes
            
        Returns:
            Request with new body
        """
        # Create new scope with modified body
        scope = original_request.scope.copy()
        
        # Update headers in scope to reflect new content length
        headers = list(scope.get("headers", []))
        
        # Remove old content-length header if present
        headers = [(name, value) for name, value in headers if name != b"content-length"]
        
        # Add new content-length header
        headers.append((b"content-length", str(len(new_body)).encode()))
        scope["headers"] = headers
        
        # Create async generator for new body
        async def new_receive():
            return {
                "type": "http.request",
                "body": new_body,
                "more_body": False
            }
        
        # Create new request with modified scope and receive
        return Request(scope, new_receive)
    
    async def _log_pseudonymization_event(
        self, 
        request: Request,
        success: bool,
        message: str
    ):
        """
        Log pseudonymization event for audit trails.
        
        Args:
            request: Original request
            success: Whether pseudonymization succeeded
            message: Event message
        """
        try:
            # Extract request metadata
            client_ip = getattr(request.client, 'host', 'unknown') if request.client else 'unknown'
            user_agent = request.headers.get('user-agent', 'unknown')
            endpoint = request.url.path
            method = request.method
            content_type = request.headers.get('content-type', 'unknown')
            
            # Get pseudonymization stats
            stats = self.pseudonymization_service.get_pseudonymization_stats()
            
            # Log structured event
            log_data = {
                "event": "pseudonymization",
                "success": success,
                "message": message,
                "request_info": {
                    "method": method,
                    "endpoint": endpoint,
                    "content_type": content_type,
                    "client_ip": client_ip,
                    "user_agent": user_agent
                },
                "pseudonymization_stats": stats
            }
            
            if success:
                logger.info(f"Pseudonymization event: {json.dumps(log_data)}")
            else:
                logger.error(f"Pseudonymization failure: {json.dumps(log_data)}")
                
        except Exception as e:
            logger.error(f"Failed to log pseudonymization event: {e}")
    
    def get_service_stats(self) -> Dict[str, Any]:
        """Get pseudonymization service statistics."""
        return self.pseudonymization_service.get_pseudonymization_stats()
    
    async def clear_old_mappings(self, older_than_days: Optional[int] = None) -> int:
        """Clear old pseudonymization mappings."""
        return self.pseudonymization_service.clear_mappings(older_than_days)


class PseudonymizationContext:
    """
    Context manager for pseudonymization operations.
    
    Provides access to the current pseudonymization service
    and allows temporary disabling of pseudonymization for
    specific operations.
    """
    
    _current_service: Optional[PseudonymizationService] = None
    _disabled: bool = False
    
    @classmethod
    def set_service(cls, service: PseudonymizationService):
        """Set the current pseudonymization service."""
        cls._current_service = service
    
    @classmethod
    def get_service(cls) -> Optional[PseudonymizationService]:
        """Get the current pseudonymization service."""
        return cls._current_service
    
    @classmethod
    @asynccontextmanager
    async def disabled(cls):
        """Context manager to temporarily disable pseudonymization."""
        original_state = cls._disabled
        cls._disabled = True
        try:
            yield
        finally:
            cls._disabled = original_state
    
    @classmethod
    def is_disabled(cls) -> bool:
        """Check if pseudonymization is currently disabled."""
        return cls._disabled


# Utility functions for manual pseudonymization
def get_current_pseudonymization_service() -> Optional[PseudonymizationService]:
    """Get the current pseudonymization service instance."""
    return PseudonymizationContext.get_service()


def pseudonymize_patient_id(patient_id: str, id_type: str = "Patient") -> str:
    """
    Manually pseudonymize a patient identifier.
    
    Args:
        patient_id: Original patient identifier
        id_type: Type of identifier
        
    Returns:
        Pseudonymized identifier
    """
    service = get_current_pseudonymization_service()
    if service:
        return service.pseudonymize_identifier(patient_id, id_type)
    else:
        logger.warning("No pseudonymization service available")
        return patient_id


def depseudonymize_patient_id(pseudonymized_id: str) -> Optional[str]:
    """
    Manually depseudonymize a patient identifier.
    
    Args:
        pseudonymized_id: Pseudonymized identifier
        
    Returns:
        Original identifier if found, None otherwise
    """
    service = get_current_pseudonymization_service()
    if service:
        return service.depseudonymize_identifier(pseudonymized_id)
    else:
        logger.warning("No pseudonymization service available")
        return None