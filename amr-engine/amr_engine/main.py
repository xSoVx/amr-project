from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .api.routes import router
from .config import get_settings
from .core.exceptions import FHIRValidationError, RulesValidationError
from .logging_setup import setup_logging


def create_app() -> FastAPI:
    setup_logging()
    settings = get_settings()
    app = FastAPI(title=settings.SERVICE_NAME, version="0.1.0")

    @app.exception_handler(RulesValidationError)
    async def rules_error_handler(request: Request, exc: RulesValidationError):
        return JSONResponse(status_code=500, content={"error": str(exc)})

    @app.exception_handler(FHIRValidationError)
    async def fhir_error_handler(request: Request, exc: FHIRValidationError):
        return JSONResponse(status_code=400, content={"resourceType": "OperationOutcome", "issue": exc.issues or [{"severity": "error", "diagnostics": exc.detail}]})

    app.include_router(router)
    return app


app = create_app()

