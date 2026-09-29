"""Call lifecycle service — create/end/list/detail + dashboard aggregation."""

from __future__ import annotations

import math
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.db.models.call import Call
from app.db.models.call_event import CallEvent
from app.db.models.contact import Contact
from app.db.models.enums import CallOutcome, CallStatus, LeadStatus
from app.schemas.dashboard import DashboardStats


async def create_call(
    session,
    *,
    phone_number: str | None,
    contact_id: int | None,
) -> Call:
    """Insert a new outbound call in ``queued`` status.

    When only *contact_id* is given, the contact's stored E.164 number is used.
    An unknown ``contact_id`` is deliberately **not** pre-validated — the foreign
    key is the source of truth (integrity error ⇒ structured 500).
    """
    number = phone_number
    if number is None:
        if contact_id is None:
            raise ValueError("phone_number or contact_id is required")
        contact = await session.get(Contact, contact_id)
        if contact is None:
            raise LookupError(f"contact {contact_id} not found")
        number = contact.phone_e164

    call = Call(phone_number=number, contact_id=contact_id, status=CallStatus.queued)
    session.add(call)
    await session.flush()
    session.add(CallEvent(call_id=call.id, event_type="call_created"))
    return call


async def end_call(session, call: Call) -> Call:
    """Close a call: ``completed`` + end_time + duration (idempotent on end)."""
    if call.status != CallStatus.completed:
        now = datetime.now(tz=UTC)
        call.end_time = now
        anchor = call.start_time or call.created_at
        if anchor is not None:
            if anchor.tzinfo is None:
                anchor = anchor.replace(tzinfo=UTC)
            call.duration_seconds = max(0, int((now - anchor).total_seconds()))
        call.status = CallStatus.completed
        session.add(CallEvent(call_id=call.id, event_type="call_ended"))
        await session.flush()
    return call


async def get_call(session, call_id: uuid.UUID) -> Call | None:
    """Load one call with all detail relationships eagerly fetched."""
    stmt = (
        select(Call)
        .where(Call.id == call_id)
        .options(
            selectinload(Call.turns),
            selectinload(Call.extracted_data),
            selectinload(Call.summary),
            selectinload(Call.events),
            selectinload(Call.contact),
        )
    )
    return await session.scalar(stmt)


async def list_calls(
    session,
    *,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    customer: str | None = None,
    status: CallStatus | None = None,
    lead_status: LeadStatus | None = None,
    followup_required: bool | None = None,
    outcome: CallOutcome | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Call], int]:
    """Return ``(calls, total)`` for the given filters — every filter optional.

    Date filters are inclusive on ``calls.created_at`` (UTC calendar dates).
    *customer* is a contact id (digits) or a case-insensitive name fragment.
    """
    filters = []
    if date_from is not None:
        filters.append(Call.created_at >= date_from)
    if date_to is not None:
        # inclusive upper bound: end of that UTC day
        day_end = date_to.replace(hour=23, minute=59, second=59, microsecond=999999)
        filters.append(Call.created_at <= day_end)
    if status is not None:
        filters.append(Call.status == status)
    if lead_status is not None:
        filters.append(Call.lead_status == lead_status)
    if followup_required is not None:
        filters.append(Call.followup_required.is_(followup_required))
    if outcome is not None:
        filters.append(Call.outcome == outcome)
    if customer:
        if customer.isdigit():
            filters.append(Call.contact_id == int(customer))
        else:
            filters.append(
                Call.contact_id.in_(select(Contact.id).where(Contact.name.ilike(f"%{customer}%")))
            )

    total = await session.scalar(select(func.count()).select_from(Call).where(*filters)) or 0
    stmt = (
        select(Call)
        .where(*filters)
        .order_by(Call.created_at.desc(), Call.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = list((await session.scalars(stmt)).all())
    return rows, int(total)


async def dashboard_stats(session) -> DashboardStats:
    """Aggregate the six headline numbers in a single query."""
    row = (
        await session.execute(
            select(
                func.count(Call.id),
                func.count().filter(Call.status == CallStatus.completed),
                func.count().filter(Call.status.in_([CallStatus.failed, CallStatus.no_answer])),
                func.count().filter(Call.outcome == CallOutcome.interested),
                func.count().filter(Call.followup_required.is_(True)),
                func.coalesce(func.avg(Call.duration_seconds), 0.0),
            )
        )
    ).one()
    total, completed, failed, interested, followups, avg_duration = row
    return DashboardStats(
        total_calls=int(total),
        completed_calls=int(completed),
        failed_calls=int(failed),
        interested_leads=int(interested),
        followups_required=int(followups),
        avg_duration_seconds=round(float(avg_duration), 1),
    )


def pages_for(total: int, page_size: int) -> int:
    """Number of pages for a total/page-size pair (at least 1)."""
    return max(1, math.ceil(total / page_size)) if page_size else 1


__all__ = [
    "create_call",
    "end_call",
    "get_call",
    "list_calls",
    "dashboard_stats",
    "pages_for",
]
