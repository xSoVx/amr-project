from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .api.routes import router
from .config import get_settings
from .core.exceptions import FHIRValidationError, RulesValidationError
try:
    from .core.tracing import init_tracing, get_tracer
    HAS_TRACING = True
    TRACING_ERROR = None
except ImportError as e:
    # Note: logger not yet available, will warn in create_app
    HAS_TRACING = False
    TRACING_ERROR = str(e)
    def init_tracing(*args, **kwargs): return None
    def get_tracer(): return None
from .logging_setup import setup_logging


def create_app() -> FastAPI:
    setup_logging()
    logger = logging.getLogger(__name__)
    settings = get_settings()
    
    # Initialize OpenTelemetry tracing if available
    tracing = None
    if HAS_TRACING:
        tracing = init_tracing(
            service_name=getattr(settings, 'SERVICE_NAME', 'amr-engine'),
            service_version="0.1.0",
            otlp_endpoint=os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT'),
            sample_rate=float(os.getenv('OTEL_TRACE_SAMPLE_RATE', '1.0'))
        )
    else:
        logger.warning(f"OpenTelemetry tracing not available: {TRACING_ERROR}")
    
    app = FastAPI(
        title="AMR Classification Engine",
        description="""
        ## Antimicrobial Resistance (AMR) Classification Microservice
        
        This service classifies antimicrobial susceptibility test results according to clinical breakpoints.
        It supports multiple input formats including FHIR R4 bundles and HL7v2 messages.
        
        ### Key Features:
        - **FHIR R4 Support**: Process FHIR observation bundles
        - **HL7v2 Support**: Parse HL7v2 OBR/OBX segments
        - **EUCAST Guidelines**: Classification based on EUCAST v2025.1
        - **Multiple Methods**: Supports both MIC and disc diffusion testing
        - **Real-time Processing**: Fast classification with comprehensive validation
        
        ### Classification Results:
        - **S** - Susceptible
        - **I** - Susceptible, increased exposure
        - **R** - Resistant
        - **RR** - Resistant, rare resistance
        
        ### Authentication:
        Some endpoints require admin authentication using the `X-Admin-Token` header.
        """,
        version="0.1.0",
        contact={
            "name": "AMR Team",
            "email": "support@amr-engine.com",
        },
        license_info={
            "name": "MIT License",
            "url": "https://opensource.org/licenses/MIT",
        },
        servers=[
            {
                "url": "http://localhost:8080",
                "description": "Development server"
            },
            {
                "url": "http://localhost:8081", 
                "description": "Docker development server"
            }
        ],
        tags_metadata=[
            {
                "name": "health",
                "description": "Health check and monitoring endpoints"
            },
            {
                "name": "classification", 
                "description": "AMR classification endpoints supporting FHIR and HL7v2"
            },
            {
                "name": "administration",
                "description": "Administrative endpoints requiring authentication"
            },
            {
                "name": "metrics",
                "description": "Prometheus metrics for monitoring"
            }
        ]
    )

    @app.exception_handler(RulesValidationError)
    async def rules_error_handler(request: Request, exc: RulesValidationError):
        from .core.schemas import ProblemDetails, OperationOutcome, OperationOutcomeIssue
        problem = ProblemDetails(
            type="https://amr-engine.com/problems/rules-validation-error",
            title="Rules Validation Error",
            status=500,
            detail=str(exc),
            operationOutcome=OperationOutcome(
                issue=[OperationOutcomeIssue(
                    severity="error",
                    code="processing",
                    diagnostics=str(exc)
                )]
            )
        )
        return JSONResponse(
            status_code=500, 
            content=problem.model_dump(),
            headers={"Content-Type": "application/problem+json"}
        )

    @app.exception_handler(FHIRValidationError)
    async def fhir_error_handler(request: Request, exc: FHIRValidationError):
        from .core.schemas import ProblemDetails, OperationOutcome, OperationOutcomeIssue
        issues = exc.issues or [{"severity": "error", "diagnostics": exc.detail}]
        operation_outcome_issues = [
            OperationOutcomeIssue(**issue) if isinstance(issue, dict) else issue 
            for issue in issues
        ]
        problem = ProblemDetails(
            type="https://amr-engine.com/problems/fhir-validation-error",
            title="FHIR Validation Error",
            status=400,
            detail=exc.detail,
            operationOutcome=OperationOutcome(issue=operation_outcome_issues)
        )
        return JSONResponse(
            status_code=400, 
            content=problem.model_dump(),
            headers={"Content-Type": "application/problem+json"}
        )

    # Instrument FastAPI with tracing if available
    if tracing:
        tracing.instrument_fastapi(app)
        tracing.instrument_requests()
    
    app.include_router(router)
    return app


app = create_app()

