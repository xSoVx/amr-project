from __future__ import annotations

import json
import logging
import os
from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, generate_latest

from .. import __version__
from ..config import get_settings
from ..core.classifier import Classifier
from ..core.fhir_adapter import parse_bundle_or_observations
from ..core.hl7v2_parser import parse_hl7v2_message
from ..core.rules_loader import RulesLoader
from ..core.schemas import ClassificationInput, ClassificationResult, OperationOutcome
from .deps import admin_auth

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
    summary="Health Check",
    description="Returns the health status of the AMR classification service",
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
    """Health check endpoint to verify service availability."""
    return {"status": "ok"}


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
                        "detail": {
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
async def classify(request: Request, payload: Any) -> List[ClassificationResult]:
    """
    Enhanced classification endpoint supporting FHIR R4, HL7v2, and direct JSON input.
    
    Automatically detects input format and processes accordingly.
    Returns AMR classification decisions based on EUCAST guidelines.
    """
    settings = get_settings()
    loader = RulesLoader()
    classifier = Classifier(loader)
    
    try:
        # Determine input format and parse accordingly
        inputs = await _parse_input(payload, request)
    except Exception as e:
        issues = [
            {"severity": "error", "code": "invalid", "diagnostics": str(e)},
        ]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=OperationOutcome(issue=issues).model_dump(),
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
def rules_reload(_: None = Depends(admin_auth)) -> dict:
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
                        "detail": {
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
async def classify_fhir(request: Request, payload: Any) -> List[ClassificationResult]:
    """
    Dedicated endpoint for FHIR Bundle and Observation processing.
    
    Parses FHIR R4 resources and extracts antimicrobial susceptibility
    test results for classification.
    """
    loader = RulesLoader()
    classifier = Classifier(loader)
    
    try:
        # Force FHIR parsing by calling parse_bundle_or_observations directly
        inputs = await parse_bundle_or_observations(payload)
    except Exception as e:
        issues = [
            {"severity": "error", "code": "invalid", "diagnostics": f"FHIR parsing error: {str(e)}"},
        ]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=OperationOutcome(issue=issues).model_dump(),
        )
    
    results: List[ClassificationResult] = []
    for item in inputs:
        res = classifier.classify(item)
        CLASSIFICATIONS.labels(res.decision).inc()
        results.append(res)
    
    return results


async def _parse_input(payload: Any, request: Request) -> List[ClassificationInput]:
    """Parse input data from various formats (FHIR, HL7v2)."""
    # Check Content-Type header to determine format
    content_type = request.headers.get("content-type", "").lower()
    
    # Handle HL7v2 messages
    if "hl7" in content_type or "x-application/hl7-v2+er7" in content_type:
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
    return await parse_bundle_or_observations(payload)


@router.post(
    "/classify/hl7v2",
    response_model=list[ClassificationResult],
    tags=["classification"],
    summary="Classify HL7v2 Messages", 
    description="""
    **Dedicated HL7v2 Message Processing**
    
    Processes HL7v2 messages containing microbiology results.
    Extracts OBR/OBX segments and classifies AMR test results.
    
    ### Supported Segments:
    - **MSH**: Message header (required)
    - **OBR**: Observation request 
    - **OBX**: Observation result (antimicrobial susceptibility data)
    
    ### Message Format:
    - Standard HL7v2 pipe-delimited format
    - Each segment on a new line
    - Must start with MSH segment
    
    ### Example HL7v2 Message:
    ```
    MSH|^~\\&|LAB|FACILITY|EMR|HOSPITAL|20240101120000||ORU^R01|12345|P|2.5
    OBR|1|||MICRO^Microbiology|||||||||||||||||||F
    OBX|1|ST|ORG^Organism||Escherichia coli||||||F
    OBX|2|NM|MIC^Amoxicillin MIC||4.0|mg/L|||||F
    ```
    """,
    response_description="Extracted and classified AMR results",
    responses={
        200: {
            "description": "Successful HL7v2 processing and classification",
            "content": {
                "application/json": {
                    "example": [{
                        "specimenId": "12345",
                        "organism": "Escherichia coli",
                        "antibiotic": "Amoxicillin",
                        "method": "MIC", 
                        "input": {
                            "organism": "Escherichia coli",
                            "antibiotic": "Amoxicillin",
                            "method": "MIC",
                            "mic_mg_L": 4.0,
                            "specimenId": "12345"
                        },
                        "decision": "S",
                        "reason": "MIC 4.0 mg/L <= breakpoint 8.0 mg/L",
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
                        "detail": {
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
def classify_hl7v2(request: Request, message: str) -> List[ClassificationResult]:
    """
    Dedicated endpoint for HL7v2 message processing.
    
    Parses HL7v2 messages and extracts antimicrobial susceptibility 
    test results for classification.
    """
    loader = RulesLoader()
    classifier = Classifier(loader)
    
    try:
        inputs = parse_hl7v2_message(message)
    except Exception as e:
        issues = [
            {"severity": "error", "code": "invalid", "diagnostics": f"HL7v2 parsing error: {str(e)}"},
        ]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=OperationOutcome(issue=issues).model_dump(),
        )
    
    results: List[ClassificationResult] = []
    for item in inputs:
        res = classifier.classify(item)
        CLASSIFICATIONS.labels(res.decision).inc()
        results.append(res)
    
    return results

