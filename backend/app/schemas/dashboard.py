"""Dashboard statistics schema."""

from __future__ import annotations

from pydantic import BaseModel, Field


class DashboardStats(BaseModel):
    total_calls: int = Field(ge=0)
    completed_calls: int = Field(ge=0)
    failed_calls: int = Field(ge=0)
    interested_leads: int = Field(ge=0)
    followups_required: int = Field(ge=0)
    avg_duration_seconds: float = Field(ge=0)
