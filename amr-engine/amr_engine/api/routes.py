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
def classify(request: Request, payload: Any) -> List[ClassificationResult]:
    settings = get_settings()
    loader = RulesLoader()
    classifier = Classifier(loader)
    try:
        inputs = parse_bundle_or_observations(payload)
    except Exception as e:  # FHIRValidationError
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

