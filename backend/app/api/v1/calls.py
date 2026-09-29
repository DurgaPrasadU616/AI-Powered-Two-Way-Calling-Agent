"""Call routes — create, end, filtered list, detail."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.models.admin import Admin
from app.db.models.enums import CallOutcome, CallStatus, LeadStatus
from app.db.session import get_db
from app.schemas.call import (
    CallCreate,
    CallDetailRead,
    CallListResponse,
    CallRead,
    PageMeta,
)
from app.services import call_service

router = APIRouter(prefix="/calls", tags=["calls"])


@router.post("", response_model=CallRead, status_code=201, summary="Queue a call")
async def create_call(
    payload: CallCreate,
    _: Admin = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> CallRead:
    try:
        call = await call_service.create_call(
            session, phone_number=payload.phone_number, contact_id=payload.contact_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await session.flush()
    return CallRead.model_validate(call)


@router.get("", response_model=CallListResponse, summary="List calls with filters")
async def list_calls(
    date_from: date | None = Query(default=None, description="inclusive UTC date"),
    date_to: date | None = Query(default=None, description="inclusive UTC date"),
    customer: str | None = Query(default=None, description="contact id or name fragment"),
    status: CallStatus | None = Query(default=None),
    lead_status: LeadStatus | None = Query(default=None),
    followup_required: bool | None = Query(default=None),
    outcome: CallOutcome | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _: Admin = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> CallListResponse:
    start = datetime.combine(date_from, datetime.min.time(), tzinfo=UTC) if date_from else None
    end = datetime.combine(date_to, datetime.min.time(), tzinfo=UTC) if date_to else None
    rows, total = await call_service.list_calls(
        session,
        date_from=start,
        date_to=end,
        customer=customer,
        status=status,
        lead_status=lead_status,
        followup_required=followup_required,
        outcome=outcome,
        page=page,
        page_size=page_size,
    )
    return CallListResponse(
        items=[CallRead.model_validate(r) for r in rows],
        meta=PageMeta(
            page=page,
            page_size=page_size,
            total=total,
            pages=call_service.pages_for(total, page_size),
        ),
    )


@router.get("/{call_id}", response_model=CallDetailRead, summary="Call detail")
async def get_call(
    call_id: uuid.UUID,
    _: Admin = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> CallDetailRead:
    call = await call_service.get_call(session, call_id)
    if call is None:
        raise HTTPException(status_code=404, detail="Call not found")
    detail = CallDetailRead.model_validate(call)
    detail.contact_name = call.contact.name if call.contact else None
    return detail


@router.post("/{call_id}/end", response_model=CallRead, summary="End a call")
async def end_call(
    call_id: uuid.UUID,
    _: Admin = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> CallRead:
    call = await call_service.get_call(session, call_id)
    if call is None:
        raise HTTPException(status_code=404, detail="Call not found")
    call = await call_service.end_call(session, call)
    return CallRead.model_validate(call)
