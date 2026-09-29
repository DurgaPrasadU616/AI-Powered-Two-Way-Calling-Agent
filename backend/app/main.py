"""FastAPI application factory — Phase 1: /health only. Routers added Phase 2+."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import get_settings
from app.core.errors import (
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.core.logging import get_logger, setup_logging

settings = get_settings()

# Initialise logging before anything else logs
setup_logging("DEBUG" if settings.APP_ENV == "development" else "INFO")
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:  # noqa: ARG001
    logger.info(
        "AI Calling Agent starting",
        extra={"env": settings.APP_ENV, "call_provider": settings.CALL_PROVIDER},
    )
    yield
    logger.info("AI Calling Agent shutting down")


app = FastAPI(
    title="AI Calling Agent",
    description=(
        "AI-Powered Two-Way Calling Agent API — "
        "outbound sales calls for Commercial RO systems (SERP Hawk)."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Global exception handlers ─────────────────────────────────────────────────
app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
app.add_exception_handler(Exception, unhandled_exception_handler)


# ── Health endpoint ───────────────────────────────────────────────────────────
@app.get("/health", tags=["health"], summary="Liveness check")
async def health_check() -> dict:
    """Return service health. Used by load-balancers and docker healthchecks."""
    return {
        "status": "ok",
        "service": "ai-calling-agent",
        "version": "0.1.0",
        "env": settings.APP_ENV,
        "call_provider": settings.CALL_PROVIDER,
    }


# ── Routers (added progressively per phase) ───────────────────────────────────
# Phase 2: from app.api.v1 import auth, contacts, calls, dashboard
# Phase 4: from app.realtime import ws_router
