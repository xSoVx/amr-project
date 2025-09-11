"""
Pact provider state routes for contract verification.

This module provides endpoints for managing provider states during
Pact contract verification, allowing tests to set up specific
scenarios and data conditions.
"""

import json
import logging
from typing import Dict, Any, Optional

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from ..core.schemas import ProblemDetails, OperationOutcome
from ...tests.pact.provider_state_manager import provider_state_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/_pact", tags=["pact-verification"])


class ProviderStateRequest(BaseModel):
    """Request model for provider state setup."""
    
    state: str = Field(..., description="Name of the provider state to set up")
    params: Optional[Dict[str, Any]] = Field(default_factory=dict, description="State parameters")


class ProviderStateResponse(BaseModel):
    """Response model for provider state operations."""
    
    state: str
    status: str = "success"
    message: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


@router.post(
    "/provider-states",
    response_model=ProviderStateResponse,
    status_code=status.HTTP_200_OK,
    summary="Set up provider state",
    description="Set up a specific provider state for contract verification testing",
    responses={
        200: {
            "description": "Provider state set up successfully",
            "content": {
                "application/json": {
                    "example": {
                        "state": "healthy patient data",
                        "status": "success",
                        "message": "Provider state configured successfully"
                    }
                }
            }
        },
        400: {
            "description": "Invalid provider state request",
            "content": {
                "application/problem+json": {
                    "example": {
                        "type": "https://tools.ietf.org/html/rfc7807",
                        "title": "Invalid Provider State",
                        "status": 400,
                        "detail": "Unknown provider state: invalid_state_name"
                    }
                }
            }
        }
    }
)
async def setup_provider_state(request: ProviderStateRequest) -> ProviderStateResponse:
    """
    Set up a provider state for contract verification.
    
    This endpoint is called by Pact verification tools to establish
    specific data and system states required for testing provider
    contract compliance.
    
    Args:
        request: Provider state setup request
        
    Returns:
        Provider state response with setup status
        
    Raises:
        HTTPException: If provider state setup fails
    """
    try:
        logger.info(f"Setting up provider state: {request.state}")
        
        # Set up the provider state using the state manager
        state_data = provider_state_manager.setup_provider_state(
            request.state, 
            request.params
        )
        
        return ProviderStateResponse(
            state=request.state,
            status="success",
            message=f"Provider state '{request.state}' configured successfully",
            data={"state_data_keys": list(state_data.keys()) if isinstance(state_data, dict) else None}
        )
        
    except ValueError as e:
        logger.error(f"Invalid provider state '{request.state}': {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ProblemDetails(
                type="https://tools.ietf.org/html/rfc7807",
                title="Invalid Provider State",
                status=400,
                detail=str(e)
            ).dict()
        )
        
    except Exception as e:
        logger.error(f"Failed to set up provider state '{request.state}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ProblemDetails(
                type="https://tools.ietf.org/html/rfc7807",
                title="Provider State Setup Error",
                status=500,
                detail=f"Failed to configure provider state: {str(e)}"
            ).dict()
        )


@router.delete(
    "/provider-states/{state_name}",
    response_model=ProviderStateResponse,
    status_code=status.HTTP_200_OK,
    summary="Clean up provider state",
    description="Clean up a specific provider state after verification testing"
)
async def cleanup_provider_state(state_name: str) -> ProviderStateResponse:
    """
    Clean up a provider state after verification.
    
    Args:
        state_name: Name of the provider state to clean up
        
    Returns:
        Cleanup status response
    """
    try:
        logger.info(f"Cleaning up provider state: {state_name}")
        
        # Clean up the provider state
        await provider_state_manager.async_cleanup_state(state_name)
        
        return ProviderStateResponse(
            state=state_name,
            status="success",
            message=f"Provider state '{state_name}' cleaned up successfully"
        )
        
    except Exception as e:
        logger.error(f"Failed to clean up provider state '{state_name}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ProblemDetails(
                type="https://tools.ietf.org/html/rfc7807",
                title="Provider State Cleanup Error",
                status=500,
                detail=f"Failed to clean up provider state: {str(e)}"
            ).dict()
        )


@router.get(
    "/provider-states",
    response_model=Dict[str, Any],
    summary="List available provider states",
    description="Get information about available provider states for testing"
)
async def list_provider_states() -> Dict[str, Any]:
    """
    List all available provider states.
    
    Returns:
        Dictionary containing available provider states and their descriptions
    """
    available_states = {
        "healthy patient data": {
            "description": "Complete FHIR Bundle with valid AMR test results",
            "format": "fhir_bundle",
            "example_consumer": "amr-consumer"
        },
        "healthy patient data for UI": {
            "description": "UI-specific patient data with complete test results",
            "format": "fhir_bundle",
            "example_consumer": "ui-service"
        },
        "invalid FHIR bundle": {
            "description": "Malformed FHIR Bundle for error testing",
            "format": "fhir_bundle",
            "expected_result": "validation_error"
        },
        "missing organism data": {
            "description": "Classification input without organism information",
            "format": "fhir_bundle",
            "expected_result": "validation_error"
        },
        "HL7v2 message with missing MIC values": {
            "description": "HL7v2 message with incomplete antimicrobial data",
            "format": "hl7v2_message",
            "expected_result": "requires_review"
        },
        "invalid organism code data": {
            "description": "FHIR Bundle with unsupported organism code",
            "format": "fhir_bundle",
            "expected_result": "rfc7807_error"
        },
        "IL-Core profile validation failure data": {
            "description": "FHIR Bundle that fails IL-Core profile validation",
            "format": "fhir_bundle",
            "profile": "IL-Core",
            "expected_result": "profile_validation_error"
        },
        "mixed format batch data": {
            "description": "Batch request with mixed FHIR and direct JSON inputs",
            "format": "batch_request",
            "example_consumer": "ui-service"
        },
        "healthy HL7v2 message": {
            "description": "Well-formed HL7v2 message with AMR data",
            "format": "hl7v2_message",
            "example_consumer": "amr-hl7v2-consumer"
        },
        "malformed HL7v2 message": {
            "description": "Invalid HL7v2 message for error testing",
            "format": "hl7v2_message",
            "expected_result": "parsing_error"
        },
        "direct classification input": {
            "description": "Valid ClassificationInput JSON object",
            "format": "direct_json",
            "example_consumer": "amr-consumer"
        },
        "invalid classification input": {
            "description": "Invalid input missing required fields",
            "format": "direct_json",
            "expected_result": "validation_error"
        }
    }
    
    return {
        "available_states": available_states,
        "total_states": len(available_states),
        "supported_formats": ["fhir_bundle", "hl7v2_message", "direct_json", "batch_request"],
        "supported_profiles": ["IL-Core", "US-Core"]
    }


@router.get(
    "/provider-states/{state_name}",
    response_model=Dict[str, Any],
    summary="Get provider state information",
    description="Get detailed information about a specific provider state"
)
async def get_provider_state_info(state_name: str) -> Dict[str, Any]:
    """
    Get information about a specific provider state.
    
    Args:
        state_name: Name of the provider state
        
    Returns:
        Detailed information about the provider state
    """
    states_info = await list_provider_states()
    available_states = states_info["available_states"]
    
    if state_name not in available_states:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ProblemDetails(
                type="https://tools.ietf.org/html/rfc7807",
                title="Provider State Not Found",
                status=404,
                detail=f"Provider state '{state_name}' is not available"
            ).dict()
        )
    
    state_info = available_states[state_name].copy()
    state_info["name"] = state_name
    
    # Add current status if state is active
    try:
        # Check if state is currently active in the state manager
        current_states = getattr(provider_state_manager, 'active_states', {})
        if state_name in current_states:
            state_info["status"] = "active"
            state_info["last_setup"] = current_states[state_name].get("setup_time")
        else:
            state_info["status"] = "inactive"
    except:
        state_info["status"] = "unknown"
    
    return state_info


@router.post(
    "/provider-states/reset",
    response_model=Dict[str, Any],
    summary="Reset all provider states",
    description="Reset all provider states to initial conditions"
)
async def reset_all_provider_states() -> Dict[str, Any]:
    """
    Reset all provider states to initial conditions.
    
    This is useful for cleaning up after test runs or preparing
    for a fresh set of verification tests.
    
    Returns:
        Reset operation status
    """
    try:
        logger.info("Resetting all provider states")
        
        # Clean up all states
        provider_state_manager.cleanup()
        
        return {
            "status": "success",
            "message": "All provider states have been reset",
            "timestamp": provider_state_manager.db_state.created_at if hasattr(provider_state_manager.db_state, 'created_at') else None
        }
        
    except Exception as e:
        logger.error(f"Failed to reset provider states: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ProblemDetails(
                type="https://tools.ietf.org/html/rfc7807",
                title="Provider State Reset Error",
                status=500,
                detail=f"Failed to reset provider states: {str(e)}"
            ).dict()
        )


@router.get(
    "/health",
    summary="Pact verification health check",
    description="Check the health of Pact verification endpoints"
)
async def pact_health_check() -> Dict[str, Any]:
    """
    Health check endpoint for Pact verification services.
    
    Returns:
        Health status information
    """
    try:
        # Check state manager health
        state_manager_healthy = provider_state_manager is not None
        
        # Check database connection if available
        db_healthy = True
        if hasattr(provider_state_manager, 'db_engine') and provider_state_manager.db_engine:
            try:
                with provider_state_manager.db_engine.connect() as conn:
                    conn.execute("SELECT 1")
            except:
                db_healthy = False
        
        # Get statistics
        stats = provider_state_manager.get_stats() if hasattr(provider_state_manager, 'get_stats') else {}
        
        overall_health = state_manager_healthy and db_healthy
        
        return {
            "status": "healthy" if overall_health else "unhealthy",
            "components": {
                "state_manager": "healthy" if state_manager_healthy else "unhealthy",
                "database": "healthy" if db_healthy else "unhealthy"
            },
            "statistics": stats,
            "endpoints": {
                "setup_state": "/_pact/provider-states",
                "list_states": "/_pact/provider-states",
                "cleanup_state": "/_pact/provider-states/{state_name}",
                "reset_all": "/_pact/provider-states/reset"
            }
        }
        
    except Exception as e:
        logger.error(f"Pact health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }


# Compatibility endpoint for Pact Ruby/CLI tools
@router.post(
    "/provider_states",
    response_model=ProviderStateResponse,
    summary="Set up provider state (Ruby compatibility)",
    description="Compatibility endpoint for Pact Ruby tools",
    include_in_schema=False
)
async def setup_provider_state_ruby_compat(request: Request) -> ProviderStateResponse:
    """
    Ruby Pact compatibility endpoint for provider state setup.
    
    This endpoint provides compatibility with Pact Ruby tools that
    may use a slightly different request format.
    """
    try:
        # Parse request body
        body = await request.json()
        
        # Extract state and params (Ruby format may be different)
        state_name = body.get("state") or body.get("providerState")
        params = body.get("params", {})
        
        if not state_name:
            raise ValueError("Missing provider state name")
        
        # Create standard request format
        pact_request = ProviderStateRequest(state=state_name, params=params)
        
        # Use the main setup function
        return await setup_provider_state(pact_request)
        
    except Exception as e:
        logger.error(f"Ruby compatibility provider state setup failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )