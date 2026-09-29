"""Post-call summary generation + persistence (Phase 3, reused by Phase 4)."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.llm import LLMClient, get_llm
from app.agent.slots import DB_COLUMNS
from app.agent.summary import CallSummaryCreate, generate_summary
from app.core.logging import get_logger
from app.db.models.call import Call
from app.db.models.call_summary import CallSummary
from app.services import call_service

logger = get_logger(__name__)


def slots_from_extracted(call: Call) -> dict[str, str | None]:
    """Map ``call_extracted_data`` columns back to agent slot names."""
    extracted = call.extracted_data
    if extracted is None:
        return {}
    return {slot: getattr(extracted, column, None) for slot, column in DB_COLUMNS.items()}


def transcript_of(call: Call) -> list[str]:
    """``["agent: ...", "customer: ..."]`` in turn order."""
    return [f"{turn.speaker.value}: {turn.message}" for turn in call.turns]


async def generate_and_store_summary(
    session: AsyncSession,
    call_id: uuid.UUID,
    *,
    llm: LLMClient | None = None,
    not_interested: bool | None = None,
) -> CallSummary | None:
    """Build the summary for *call_id*, upsert ``call_summaries`` and mirror
    outcome/lead_status/followup_required onto ``calls``.

    Returns the persisted row, or ``None`` when the call does not exist.
    Never raises: falls back to the rule-based builder on any LLM problem.
    """
    call = await call_service.get_call(session, call_id)
    if call is None:
        logger.warning("Summary requested for unknown call", extra={"call_id": str(call_id)})
        return None

    slots = slots_from_extracted(call)
    transcript = transcript_of(call)
    data, source = await generate_summary(
        llm if llm is not None else get_llm(),
        slots,
        transcript,
        not_interested=not_interested,
    )
    _persist(call, data)
    await session.flush()
    logger.info(
        "Summary generated",
        extra={"call_id": str(call_id), "source": source, "outcome": data.outcome.value},
    )
    return call.summary


def _persist(call: Call, data: CallSummaryCreate) -> None:
    summary = call.summary
    if summary is None:
        summary = CallSummary(call_id=call.id)
        call.summary = summary
    summary.summary = data.summary
    summary.key_requirements = data.key_requirements
    summary.customer_intent = data.customer_intent
    summary.important_points = data.important_points
    summary.followup_actions = data.followup_actions
    summary.outcome = data.outcome
    summary.lead_status = data.lead_status
    summary.followup_required = data.followup_required
    # mirror headline fields onto the call row itself
    call.outcome = data.outcome
    call.lead_status = data.lead_status
    call.followup_required = data.followup_required


__all__ = [
    "generate_and_store_summary",
    "slots_from_extracted",
    "transcript_of",
]
