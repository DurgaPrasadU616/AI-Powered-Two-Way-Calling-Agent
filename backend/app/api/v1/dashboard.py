"""Dashboard route — headline call metrics."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.models.admin import Admin
from app.db.session import get_db
from app.schemas.dashboard import DashboardStats
from app.services import call_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=DashboardStats, summary="Dashboard statistics")
async def stats(
    _: Admin = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> DashboardStats:
    return await call_service.dashboard_stats(session)
