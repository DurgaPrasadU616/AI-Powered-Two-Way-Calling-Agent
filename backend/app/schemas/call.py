"""Call schemas — create, list (filters + pagination), detail and sub-resources."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.db.models.enums import CallOutcome, CallStatus, LeadStatus, Speaker
from app.schemas.contact import validate_e164


# ── Create ─────────────────────────────────────────────────────────────────────
class CallCreate(BaseModel):
    """Start an outbound call. Either provide phone_number, or a contact_id
    whose stored number will be used."""

    phone_number: str | None = Field(default=None, max_length=20, examples=["+919876543210"])
    contact_id: int | None = Field(
        default=None, examples=[1], description="ID of existing contact to call"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "contact_id": 1,
                "phone_number": "+919876543210",
            }
        }
    }

    @field_validator("phone_number")
    @classmethod
    def _phone_is_e164(cls, value: str | None) -> str | None:
        return None if value is None else validate_e164(value)


# ── Read ──────────────────────────────────────────────────────────────────────
class CallRead(BaseModel):
    id: uuid.UUID
    contact_id: int | None
    phone_number: str
    direction: str
    provider: str
    status: CallStatus
    outcome: CallOutcome | None
    start_time: datetime | None
    end_time: datetime | None
    duration_seconds: int | None
    lead_status: LeadStatus
    followup_required: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class PageMeta(BaseModel):
    page: int
    page_size: int
    total: int
    pages: int


class CallListResponse(BaseModel):
    items: list[CallRead]
    meta: PageMeta


# ── Detail sub-resources ──────────────────────────────────────────────────────
class CallTurnRead(BaseModel):
    turn_index: int
    speaker: Speaker
    message: str
    confidence: float | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ExtractedDataRead(BaseModel):
    customer_name: str | None
    company_name: str | None
    requirement: str | None
    ro_capacity_lph: str | None
    location: str | None
    application: str | None
    budget: str | None
    timeline: str | None
    additional_requirements: str | None
    raw_json: dict[str, Any] | None
    updated_at: datetime

    model_config = {"from_attributes": True}


class SummaryRead(BaseModel):
    summary: str | None
    key_requirements: Any
    customer_intent: str | None
    important_points: Any
    followup_actions: Any
    outcome: CallOutcome | None
    lead_status: LeadStatus | None
    followup_required: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class CallEventRead(BaseModel):
    event_type: str
    detail: dict[str, Any] | None
    created_at: datetime

    model_config = {"from_attributes": True}


class CallDetailRead(CallRead):
    contact_name: str | None = None
    turns: list[CallTurnRead] = []
    extracted_data: ExtractedDataRead | None = None
    summary: SummaryRead | None = None
    events: list[CallEventRead] = []
