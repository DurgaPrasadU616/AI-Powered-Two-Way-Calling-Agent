"""Global exception handlers — never expose stack traces to clients."""

from __future__ import annotations

import json
from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger

logger = get_logger(__name__)


def _jsonable(value: Any) -> Any:
    """Recursively make a value JSON-safe.

    Pydantic puts the original exception objects (e.g. ValueError) into each
    error's ``ctx`` — those are not serialisable and must be stringified.
    """
    return json.loads(json.dumps(value, default=str))


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    logger.warning(
        "HTTP error",
        extra={"status_code": exc.status_code, "detail": exc.detail, "path": str(request.url)},
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "status_code": exc.status_code},
        headers=exc.headers,  # preserves WWW-Authenticate / Retry-After
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    errors = _jsonable(exc.errors())
    logger.warning(
        "Validation error",
        extra={"path": str(request.url), "errors": errors},
    )
    return JSONResponse(
        status_code=422,
        content={"detail": errors, "status_code": 422},
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "Unhandled exception",
        extra={"path": str(request.url), "error": str(exc)},
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "status_code": 500},
    )
