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


@router.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@router.get("/version")
def version() -> dict:
    return {"service": get_settings().SERVICE_NAME, "version": __version__}


@router.get("/metrics")
def metrics() -> Response:
    data = generate_latest(registry)
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)


@router.post("/classify", response_model=list[ClassificationResult])
async def classify(request: Request, payload: Any) -> List[ClassificationResult]:
    """Enhanced classification endpoint supporting FHIR and HL7v2."""
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


@router.post("/rules/dry-run", response_model=ClassificationResult)
def rules_dry_run(item: ClassificationInput) -> ClassificationResult:
    loader = RulesLoader()
    classifier = Classifier(loader)
    return classifier.classify(item)


@router.post("/admin/rules/reload")
def rules_reload(_: None = Depends(admin_auth)) -> dict:
    loader = RulesLoader()
    loader.load()
    return {"status": "ok", "sources": loader.ruleset.sources if loader.ruleset else []}


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


@router.post("/classify/hl7v2", response_model=list[ClassificationResult])
def classify_hl7v2(request: Request, message: str) -> List[ClassificationResult]:
    """Dedicated endpoint for HL7v2 message processing."""
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

