"""API v1 — aggregated router mounted at /api/v1 (auth is mounted at root too)."""

from fastapi import APIRouter

from app.api.v1 import auth, calls, contacts, dashboard

api_router = APIRouter()
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(contacts.router, tags=["contacts"])
api_router.include_router(calls.router, tags=["calls"])
api_router.include_router(dashboard.router, tags=["dashboard"])

__all__ = ["api_router"]
