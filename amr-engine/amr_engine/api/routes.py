from __future__ import annotations

import json
import logging
import os
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.openapi.utils import get_openapi
import yaml
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, generate_latest

from .. import __version__
from ..config import get_settings
from ..core.classifier import Classifier
from ..core.fhir_adapter import parse_bundle_or_observations
from ..core.fhir_profiles import FHIRProfileValidator
from ..core.metrics import metrics
from ..core.hl7v2_parser import parse_hl7v2_message
from ..core.rules_loader import RulesLoader
from ..core.schemas import ClassificationInput, ClassificationResult, OperationOutcome, ProblemDetails, OperationOutcomeIssue
from .deps import admin_auth, require_admin_auth
try:
    from ..cache.redis_cache import get_cache_manager
    HAS_CACHE = True
except ImportError:
    HAS_CACHE = False
    def get_cache_manager(): return None

logger = logging.getLogger(__name__)

router = APIRouter()

registry = CollectorRegistry()
CLASSIFICATIONS = Counter(
    "amr_classifications_total",
    "Total AMR classifications",
    labelnames=("decision",),
    registry=registry,
)


@router.get(
    "/healthz",
    tags=["health"],
    summary="Health Check (Legacy)",
    description="Legacy health check endpoint for backward compatibility",
    response_description="Service health status",
    responses={
        200: {
            "description": "Service is healthy",
            "content": {
                "application/json": {
                    "example": {"status": "ok"}
                }
            }
        }
    }
)
def healthz() -> dict:
    """Legacy health check endpoint to verify service availability."""
    return {"status": "ok"}


@router.get(
    "/health",
    tags=["health"],
    summary="Health Check",
    description="Returns the health status of the AMR classification service",
    response_description="Service health status",
    responses={
        200: {
            "description": "Service is healthy",
            "content": {
                "application/json": {
                    "example": {"status": "healthy"}
                }
            }
        }
    }
)
def health() -> dict:
    """Health check endpoint to verify service availability."""
    health_info = {"status": "healthy"}
    
    # Add cache health information if available
    if HAS_CACHE:
        try:
            cache_manager = get_cache_manager()
            if cache_manager:
                cache_health = cache_manager.get_cache_health()
                health_info["cache"] = cache_health
        except Exception as e:
            health_info["cache"] = {"enabled": False, "error": str(e)}
    else:
        health_info["cache"] = {"enabled": False, "status": "unavailable"}
    
    return health_info


@router.post(
    "/validate/fhir",
    tags=["validation"],
    summary="Validate FHIR Bundle/Resources",
    description="""
    **Validate FHIR Bundle or individual resources against profile packs**
    
    Supports comprehensive validation against:
    - **US-Core** profiles for US healthcare interoperability
    - **IL-Core** profiles for Israeli healthcare standards  
    - **IPS** (International Patient Summary) profiles
    - **Base** FHIR R4 profiles
    
    ### Features:
    - Structural validation (cardinality, data types)
    - Terminology validation (LOINC, SNOMED CT)
    - MustSupport element checking
    - Profile-specific constraints
    
    ### Profile Pack Selection:
    - Header: `X-FHIR-Profile-Pack: US-Core|IL-Core|IPS|Base`
    - Query parameter: `profile_pack=US-Core`
    - Default: Configured profile pack
    """,
    responses={
        200: {
            "description": "Validation completed",
            "content": {
                "application/json": {
                    "example": {
                        "bundle_valid": True,
                        "profile_pack": "US-Core",
                        "total_resources": 3,
                        "valid_resources": 3,
                        "invalid_resources": 0,
                        "summary_errors": [],
                        "summary_warnings": [],
                        "recommendations": []
                    }
                }
            }
        },
        400: {
            "description": "Invalid FHIR bundle or validation error"
        }
    }
)
async def validate_fhir_bundle(
    request: Request,
    profile_pack: Optional[str] = None
) -> Dict[str, Any]:
    """Validate FHIR Bundle or resources against specified profile pack."""
    
    try:
        # Get bundle from request body
        bundle = await request.json()
        
        # Determine profile pack
        selected_profile_pack = _get_profile_pack_selection(request, profile_pack)
        
        # Create profile validator for selected pack
        validator = FHIRProfileValidator(profile_pack=selected_profile_pack)
        
        # Perform validation
        results = await validator.validate_bundle_against_profile_pack(bundle)
        
        # Add validation summary
        results["validation_summary"] = validator.get_validation_summary()
        
        return results
        
    except json.JSONDecodeError as e:
        problem = ProblemDetails(
            type="https://amr-engine.com/problems/json-parse-error",
            title="JSON Parsing Error",
            status=400,
            detail=f"Invalid JSON payload: {str(e)}"
        )
        raise HTTPException(status_code=400, detail=problem.model_dump())
        
    except Exception as e:
        problem = ProblemDetails(
            type="https://amr-engine.com/problems/validation-error",
            title="FHIR Validation Error", 
            status=400,
            detail=f"Validation failed: {str(e)}"
        )
        raise HTTPException(status_code=400, detail=problem.model_dump())


@router.get(
    "/ready",
    tags=["health"],
    summary="Readiness Check",
    description="Returns the readiness status of the AMR classification service - checks if the service can handle requests",
    response_description="Service readiness status",
    responses={
        200: {
            "description": "Service is ready",
            "content": {
                "application/json": {
                    "example": {"status": "ready"}
                }
            }
        },
        503: {
            "description": "Service is not ready",
            "content": {
                "application/json": {
                    "example": {"status": "not ready", "reason": "Rules not loaded"}
                }
            }
        }
    }
)
def ready() -> dict:
    """Readiness check endpoint to verify service can handle requests."""
    try:
        # Check if rules can be loaded
        loader = RulesLoader()
        if not loader.ruleset:
            loader.load()
        if not loader.ruleset:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"status": "not ready", "reason": "Rules not loaded"}
            )
        return {"status": "ready"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "not ready", "reason": str(e)}
        )


@router.get(
    "/version",
    tags=["health"],
    summary="Service Version",
    description="Returns the service name and version information",
    response_description="Service version details",
    responses={
        200: {
            "description": "Service version information",
            "content": {
                "application/json": {
                    "example": {
                        "service": "amr-engine", 
                        "version": "0.1.0"
                    }
                }
            }
        }
    }
)
def version() -> dict:
    """Get service version and build information."""
    return {"service": get_settings().SERVICE_NAME, "version": __version__}


@router.get(
    "/openapi.yaml",
    tags=["health"],
    summary="OpenAPI Specification (YAML)",
    description="Returns the OpenAPI specification in YAML format for API documentation and client generation",
    response_description="OpenAPI specification in YAML format",
    responses={
        200: {
            "description": "OpenAPI specification",
            "content": {
                "application/x-yaml": {
                    "example": "openapi: 3.0.2\ninfo:\n  title: AMR Classification Engine\n  version: 0.1.0"
                }
            }
        }
    }
)
def openapi_yaml(request: Request) -> Response:
    """Get OpenAPI specification in YAML format for API documentation."""
    # Get the FastAPI app from the request
    from ..main import app
    
    # Generate the OpenAPI JSON
    openapi_schema = app.openapi()
    
    # Convert to YAML
    yaml_content = yaml.dump(openapi_schema, default_flow_style=False, sort_keys=False)
    
    return Response(content=yaml_content, media_type="application/x-yaml")


@router.get(
    "/metrics",
    tags=["metrics"],
    summary="Prometheus Metrics",
    description="Returns Prometheus-formatted metrics for monitoring AMR classifications",
    response_description="Prometheus metrics in text format",
    responses={
        200: {
            "description": "Prometheus metrics",
            "content": {
                "text/plain": {
                    "example": "# HELP amr_classifications_total Total AMR classifications\n# TYPE amr_classifications_total counter\namr_classifications_total{decision=\"S\"} 42\namr_classifications_total{decision=\"R\"} 18"
                }
            }
        }
    }
)
def metrics() -> Response:
    """Prometheus metrics endpoint for monitoring classification statistics."""
    data = generate_latest(registry)
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)


@router.post(
    "/classify",
    response_model=list[ClassificationResult],
    tags=["classification"],
    summary="Classify AMR Test Results",
    description="""
    **Universal AMR Classification Endpoint**
    
    This endpoint accepts multiple input formats and automatically detects the format:
    - **FHIR R4 Bundle**: Send FHIR Bundle containing Observation resources
    - **FHIR Observations**: Send array of FHIR Observation resources  
    - **HL7v2 Messages**: Send raw HL7v2 messages (auto-detected by MSH segment)
    - **Raw JSON**: Send ClassificationInput objects directly
    
    ### Input Detection:
    - Content-Type: `application/x-hl7-v2+er7` → HL7v2 processing
    - String starting with `MSH|` → HL7v2 processing  
    - FHIR Bundle/Observations → FHIR processing
    - Direct JSON → Raw processing
    
    ### FHIR Profile Pack Selection:
    - **Header**: `X-FHIR-Profile-Pack: IL-Core` (highest priority)
    - **Query Parameter**: `profile_pack=US-Core` (medium priority)  
    - **Default**: Server configuration (lowest priority)
    - **Supported Packs**: Base, IL-Core, US-Core, IPS
    
    ### Required Fields:
    - `organism` or `organism_snomed`: Bacterial species
    - `antibiotic` or `antibiotic_atc`: Antimicrobial agent
    - `method`: Either "MIC" or "DISC"
    - `mic_mg_L` (for MIC) or `disc_zone_mm` (for disc diffusion)
    """,
    response_description="List of classification results with decisions and reasoning",
    responses={
        200: {
            "description": "Successful classification",
            "content": {
                "application/json": {
                    "examples": {
                        "mic_susceptible": {
                            "summary": "MIC - Susceptible Result",
                            "value": [{
                                "specimenId": "SPEC-001",
                                "organism": "Escherichia coli",
                                "antibiotic": "Amoxicillin", 
                                "method": "MIC",
                                "input": {
                                    "organism": "Escherichia coli",
                                    "antibiotic": "Amoxicillin",
                                    "method": "MIC",
                                    "mic_mg_L": 4.0
                                },
                                "decision": "S",
                                "reason": "MIC 4.0 mg/L <= breakpoint 8.0 mg/L",
                                "ruleVersion": "EUCAST v2025.1"
                            }]
                        },
                        "disc_resistant": {
                            "summary": "Disc - Resistant Result", 
                            "value": [{
                                "specimenId": "SPEC-002",
                                "organism": "Staphylococcus aureus",
                                "antibiotic": "Ciprofloxacin",
                                "method": "DISC", 
                                "input": {
                                    "organism": "Staphylococcus aureus",
                                    "antibiotic": "Ciprofloxacin",
                                    "method": "DISC",
                                    "disc_zone_mm": 15.0
                                },
                                "decision": "R",
                                "reason": "Zone 15 mm < breakpoint 20 mm", 
                                "ruleVersion": "EUCAST v2025.1"
                            }]
                        }
                    }
                }
            }
        },
        400: {
            "description": "Invalid input format or missing required fields",
            "content": {
                "application/json": {
                    "example": {
                        "type": "https://amr-engine.com/problems/input-validation-error",
                        "title": "Input Validation Error",
                        "status": 400,
                        "detail": "Missing required field: organism",
                        "operationOutcome": {
                            "resourceType": "OperationOutcome",
                            "issue": [{
                                "severity": "error",
                                "code": "invalid",
                                "diagnostics": "Missing required field: organism"
                            }]
                        }
                    }
                }
            }
        }
    }
)
async def classify(request: Request, payload: Any, profile_pack: Optional[str] = None) -> List[ClassificationResult]:
    """
    Enhanced classification endpoint supporting FHIR R4, HL7v2, and direct JSON input.
    
    Automatically detects input format and processes accordingly.
    Returns AMR classification decisions based on EUCAST guidelines.
    """
    settings = get_settings()
    loader = RulesLoader()
    classifier = Classifier(loader)
    
    try:
        # Determine FHIR profile pack from header, query param, or default
        selected_profile_pack = _get_profile_pack_selection(request, profile_pack)
        if selected_profile_pack:
            metrics.record_profile_selection(
                profile_pack=selected_profile_pack,
                selection_source=_get_profile_pack_source(request, profile_pack),
                tenant_id=request.headers.get("X-Tenant-ID")
            )
        
        # Determine input format and parse accordingly
        inputs = await _parse_input(payload, request, selected_profile_pack)
    except Exception as e:
        operation_outcome = OperationOutcome(
            issue=[OperationOutcomeIssue(
                severity="error", 
                code="invalid", 
                diagnostics=str(e)
            )]
        )
        problem = ProblemDetails(
            type="https://amr-engine.com/problems/input-validation-error",
            title="Input Validation Error",
            status=400,
            detail=str(e),
            operationOutcome=operation_outcome
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=problem,
            headers={"Content-Type": "application/problem+json"}
        )

    results: List[ClassificationResult] = []
    for item in inputs:
        res = classifier.classify(item)
        CLASSIFICATIONS.labels(res.decision).inc()
        results.append(res)
    return results


@router.post(
    "/rules/dry-run",
    response_model=ClassificationResult,
    tags=["classification"],
    summary="Test Classification Rules",
    description="""
    **Test Rule Classification (Dry Run)**
    
    Test the classification rules without affecting metrics or logging.
    Useful for validating rule behavior with specific input combinations.
    
    ### Use Cases:
    - Rule validation during development
    - Testing edge cases
    - Debugging classification logic
    - Integration testing
    """,
    response_description="Single classification result",
    responses={
        200: {
            "description": "Successful classification",
            "content": {
                "application/json": {
                    "example": {
                        "specimenId": "TEST-001",
                        "organism": "Escherichia coli",
                        "antibiotic": "Ciprofloxacin",
                        "method": "MIC",
                        "input": {
                            "organism": "Escherichia coli",
                            "antibiotic": "Ciprofloxacin", 
                            "method": "MIC",
                            "mic_mg_L": 0.5
                        },
                        "decision": "S",
                        "reason": "MIC 0.5 mg/L <= breakpoint 0.5 mg/L",
                        "ruleVersion": "EUCAST v2025.1"
                    }
                }
            }
        }
    }
)
def rules_dry_run(item: ClassificationInput) -> ClassificationResult:
    """
    Dry run classification for testing rules without metrics impact.
    
    Accepts a single ClassificationInput and returns the classification
    result without incrementing counters or generating logs.
    """
    loader = RulesLoader()
    classifier = Classifier(loader)
    return classifier.classify(item)


@router.post(
    "/admin/rules/reload",
    tags=["administration"],
    summary="Reload Classification Rules",
    description="""
    **Reload AMR Classification Rules**
    
    Reloads the classification rules from the configured rule files.
    Requires admin authentication via `X-Admin-Token` header.
    
    ### Security:
    - **Admin Token Required**: Must provide valid admin token in request header
    - **Header**: `X-Admin-Token: your-admin-token`
    
    ### Use Cases:
    - Update rules without service restart
    - Apply new EUCAST guideline versions
    - Hot-reload rule modifications in development
    """,
    response_description="Rule reload status and sources",
    responses={
        200: {
            "description": "Rules reloaded successfully",
            "content": {
                "application/json": {
                    "example": {
                        "status": "ok",
                        "sources": ["amr_engine/rules/eucast_v_2025_1.yaml"]
                    }
                }
            }
        },
        403: {
            "description": "Authentication required - missing or invalid admin token",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Authentication required"
                    }
                }
            }
        }
    }
)
def rules_reload(admin_user: dict = Depends(require_admin_auth)) -> dict:
    """
    Reload classification rules from configured sources.
    
    Requires admin authentication. Reloads rules without service restart
    allowing for dynamic rule updates in production environments.
    """
    loader = RulesLoader()
    loader.load()
    return {"status": "ok", "sources": loader.ruleset.sources if loader.ruleset else []}


@router.post(
    "/classify/fhir",
    response_model=list[ClassificationResult],
    tags=["classification"],
    summary="Classify FHIR Bundle/Observations",
    description="""
    **Dedicated FHIR R4 Processing**
    
    Processes FHIR R4 Bundles or arrays of Observation resources containing
    antimicrobial susceptibility test results.
    
    ### Supported FHIR Resources:
    - **Bundle**: FHIR Bundle containing Observation resources
    - **Observation Array**: Array of FHIR Observation resources
    - **Single Observation**: Single FHIR Observation resource
    
    ### FHIR Profile Pack Selection:
    - **Header**: `X-FHIR-Profile-Pack: IL-Core` (highest priority)
    - **Query Parameter**: `profile_pack=US-Core` (medium priority)  
    - **Default**: Server configuration (lowest priority)
    - **Supported Packs**: Base, IL-Core, US-Core, IPS
    
    ### FHIR Observation Requirements:
    - **code**: Must contain antimicrobial susceptibility test codes
    - **subject**: Patient reference (optional)
    - **specimen**: Specimen reference (optional)
    - **valueQuantity**: MIC value with units
    - **component**: For organism identification and other metadata
    
    ### Example FHIR Bundle:
    ```json
    {
      "resourceType": "Bundle",
      "type": "collection",
      "entry": [
        {
          "resource": {
            "resourceType": "Observation",
            "status": "final",
            "code": {
              "coding": [
                {
                  "system": "http://loinc.org",
                  "code": "87181-4",
                  "display": "Amoxicillin [Susceptibility]"
                }
              ]
            },
            "subject": {
              "reference": "Patient/123"
            },
            "valueQuantity": {
              "value": 4.0,
              "unit": "mg/L"
            },
            "component": [
              {
                "code": {
                  "coding": [
                    {
                      "system": "http://snomed.info/sct",
                      "code": "264395009",
                      "display": "Microorganism"
                    }
                  ]
                },
                "valueCodeableConcept": {
                  "coding": [
                    {
                      "system": "http://snomed.info/sct", 
                      "code": "112283007",
                      "display": "Escherichia coli"
                    }
                  ]
                }
              }
            ]
          }
        }
      ]
    }
    ```
    """,
    response_description="Extracted and classified AMR results from FHIR data",
    responses={
        200: {
            "description": "Successful FHIR processing and classification",
            "content": {
                "application/json": {
                    "example": [{
                        "specimenId": "Bundle-123",
                        "organism": "Escherichia coli",
                        "antibiotic": "Amoxicillin",
                        "method": "MIC",
                        "input": {
                            "organism": "Escherichia coli",
                            "antibiotic": "Amoxicillin",
                            "method": "MIC",
                            "mic_mg_L": 4.0,
                            "specimenId": "Bundle-123"
                        },
                        "decision": "S",
                        "reason": "MIC 4.0 mg/L <= breakpoint 8.0 mg/L",
                        "ruleVersion": "EUCAST v2025.1"
                    }]
                }
            }
        },
        400: {
            "description": "Invalid FHIR format or missing required elements",
            "content": {
                "application/json": {
                    "example": {
                        "type": "https://amr-engine.com/problems/fhir-parsing-error",
                        "title": "FHIR Parsing Error",
                        "status": 400,
                        "detail": "FHIR parsing error: Missing Observation resources",
                        "operationOutcome": {
                            "resourceType": "OperationOutcome",
                            "issue": [{
                                "severity": "error",
                                "code": "invalid",
                                "diagnostics": "FHIR parsing error: Missing Observation resources"
                            }]
                        }
                    }
                }
            }
        }
    }
)
async def classify_fhir(request: Request, payload: Any, profile_pack: Optional[str] = None) -> List[ClassificationResult]:
    """
    Dedicated endpoint for FHIR Bundle and Observation processing.
    
    Parses FHIR R4 resources and extracts antimicrobial susceptibility
    test results for classification.
    """
    loader = RulesLoader()
    classifier = Classifier(loader)
    
    try:
        # Determine FHIR profile pack from header, query param, or default
        selected_profile_pack = _get_profile_pack_selection(request, profile_pack)
        if selected_profile_pack:
            metrics.record_profile_selection(
                profile_pack=selected_profile_pack,
                selection_source=_get_profile_pack_source(request, profile_pack),
                tenant_id=request.headers.get("X-Tenant-ID")
            )
        
        # Force FHIR parsing by calling parse_bundle_or_observations directly
        inputs = await parse_bundle_or_observations(payload, profile_pack=selected_profile_pack)
    except Exception as e:
        operation_outcome = OperationOutcome(
            issue=[OperationOutcomeIssue(
                severity="error", 
                code="invalid", 
                diagnostics=f"FHIR parsing error: {str(e)}"
            )]
        )
        problem = ProblemDetails(
            type="https://amr-engine.com/problems/fhir-parsing-error",
            title="FHIR Parsing Error",
            status=400,
            detail=f"FHIR parsing error: {str(e)}",
            operationOutcome=operation_outcome
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=problem,
            headers={"Content-Type": "application/problem+json"}
        )
    
    results: List[ClassificationResult] = []
    for item in inputs:
        res = classifier.classify(item)
        CLASSIFICATIONS.labels(res.decision).inc()
        results.append(res)
    
    return results


def _get_profile_pack_selection(request: Request, query_param: Optional[str] = None) -> Optional[str]:
    """Determine FHIR profile pack from header, query param, or default."""
    from ..config import get_settings, ProfilePack
    
    # Priority order: X-FHIR-Profile-Pack header > query param > config default
    profile_pack = request.headers.get("X-FHIR-Profile-Pack") or query_param
    
    if profile_pack:
        # Validate against allowed values
        valid_packs = {"IL-Core", "US-Core", "IPS", "Base"}
        if profile_pack in valid_packs:
            return profile_pack
        else:
            # Fall back to default if invalid value provided
            return get_settings().FHIR_PROFILE_PACK
    
    return get_settings().FHIR_PROFILE_PACK


def _get_profile_pack_source(request: Request, query_param: Optional[str] = None) -> str:
    """Determine the source of profile pack selection for metrics."""
    if request.headers.get("X-FHIR-Profile-Pack"):
        return "header"
    elif query_param:
        return "query_param"
    else:
        return "default"


async def _parse_input(payload: Any, request: Request, profile_pack: Optional[str] = None) -> List[ClassificationInput]:
    """Parse input data from various formats (FHIR, HL7v2)."""
    # Check Content-Type header to determine format
    content_type = request.headers.get("content-type", "").lower()
    
    # Handle HL7v2 messages
    if any(hl7_type in content_type for hl7_type in [
        "hl7", "application/hl7-v2", "application/x-hl7", "x-application/hl7-v2+er7"
    ]):
        if isinstance(payload, str):
            return parse_hl7v2_message(payload)
        else:
            raise ValueError("HL7v2 input must be text/string format")
    
    # Handle raw HL7v2 text (auto-detection)
    if isinstance(payload, str):
        # Check for HL7v2 message structure
        lines = payload.strip().split('\n')
        if lines and lines[0].startswith('MSH|'):
            return parse_hl7v2_message(payload)
    
    # Default to FHIR parsing
    return await parse_bundle_or_observations(payload, profile_pack=profile_pack)


@router.post(
    "/classify/hl7v2",
    response_model=list[ClassificationResult],
    tags=["classification"],
    summary="Classify HL7v2 Messages", 
    description="""
    **Dedicated HL7v2 Message Processing**
    
    Processes HL7v2 messages containing microbiology results.
    Extracts OBR/OBX segments and classifies AMR test results.
    
    ### Content-Type Support:
    - `application/hl7-v2` (preferred)
    - `text/plain` (HL7v2 text format)
    - `application/x-hl7` (alternative)
    
    ### Supported Segments:
    - **MSH**: Message header (required)
    - **PID**: Patient identification
    - **OBR**: Observation request 
    - **OBX**: Observation result (antimicrobial susceptibility data)
    
    ### Message Format:
    - Standard HL7v2 pipe-delimited format
    - Segments separated by \\r (carriage return) or \\n (newline)
    - Must start with MSH segment
    
    ### Example HL7v2 Message:
    ```
    MSH|^~\\&|LAB|FACILITY|EMR|HOSPITAL|20240101120000||ORU^R01|MSG12345|P|2.5\\r
    PID|1||PATIENT123^^^MRN^MR||DOE^JOHN||||||||||||ACCT456\\r
    OBR|1|||MICRO^Microbiology Culture||||||||||SPEC789|||||||||F\\r
    OBX|1|ST|ORG^Organism||Escherichia coli||||||F\\r
    OBX|2|NM|MIC^Ampicillin MIC||32|mg/L|R|||F\\r
    OBX|3|NM|MIC^Ciprofloxacin MIC||0.5|mg/L|S|||F
    ```
    
    ### Usage Example:
    ```bash
    curl -X POST "http://localhost:8080/classify/hl7v2" \\
         -H "Content-Type: application/hl7-v2" \\
         -d "MSH|^~\\&|LAB|FACILITY|EMR|HOSPITAL|20240101120000||ORU^R01|MSG12345|P|2.5\\rPID|1||PATIENT123|||DOE^JOHN\\rOBR|1|||MICRO^Microbiology\\rOBX|1|ST|ORG||Escherichia coli||||||F\\rOBX|2|NM|MIC^Ampicillin||32|mg/L|R|||F"
    ```
    """,
    response_description="Extracted and classified AMR results with pseudonymized identifiers",
    responses={
        200: {
            "description": "Successful HL7v2 processing and classification",
            "content": {
                "application/json": {
                    "example": [{
                        "specimenId": "FINAL-SP-A1B2C3D4",
                        "organism": "Escherichia coli",
                        "antibiotic": "Ampicillin",
                        "method": "MIC", 
                        "input": {
                            "organism": "Escherichia coli",
                            "antibiotic": "Ampicillin",
                            "method": "MIC",
                            "mic_mg_L": 32.0,
                            "specimenId": "FINAL-SP-A1B2C3D4"
                        },
                        "decision": "R",
                        "reason": "MIC 32.0 mg/L > breakpoint 8.0 mg/L",
                        "ruleVersion": "EUCAST v2025.1"
                    }]
                }
            }
        },
        400: {
            "description": "Invalid HL7v2 message format",
            "content": {
                "application/json": {
                    "example": {
                        "type": "https://amr-engine.com/problems/hl7v2-parsing-error",
                        "title": "HL7v2 Parsing Error",
                        "status": 400,
                        "detail": "HL7v2 parsing error: Missing MSH segment",
                        "operationOutcome": {
                            "resourceType": "OperationOutcome",
                            "issue": [{
                                "severity": "error", 
                                "code": "invalid",
                                "diagnostics": "HL7v2 parsing error: Missing MSH segment"
                            }]
                        }
                    }
                }
            }
        }
    }
)
async def classify_hl7v2(request: Request) -> List[ClassificationResult]:
    """
    Dedicated endpoint for HL7v2 message processing.
    
    Parses HL7v2 messages and extracts antimicrobial susceptibility 
    test results for classification.
    """
    # Read HL7v2 message from request body
    message_bytes = await request.body()
    message = message_bytes.decode('utf-8')
    
    loader = RulesLoader()
    classifier = Classifier(loader)
    
    try:
        inputs = parse_hl7v2_message(message)
    except Exception as e:
        operation_outcome = OperationOutcome(
            issue=[OperationOutcomeIssue(
                severity="error", 
                code="invalid", 
                diagnostics=f"HL7v2 parsing error: {str(e)}"
            )]
        )
        problem = ProblemDetails(
            type="https://amr-engine.com/problems/hl7v2-parsing-error",
            title="HL7v2 Parsing Error",
            status=400,
            detail=f"HL7v2 parsing error: {str(e)}",
            operationOutcome=operation_outcome
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=problem,
            headers={"Content-Type": "application/problem+json"}
        )
    
    results: List[ClassificationResult] = []
    for item in inputs:
        res = classifier.classify(item)
        CLASSIFICATIONS.labels(res.decision).inc()
        results.append(res)
    
    return results

