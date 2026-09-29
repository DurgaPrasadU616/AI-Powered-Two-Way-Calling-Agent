"""Post-call summary — Pydantic contract, rule-based builder, LLM generator.

The Pydantic model is the single source of truth: whatever path produced the
data (LLM JSON or deterministic fallback) must validate against it before it
may be persisted (audit D18).
"""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, Field

from app.agent.llm import LLMClient
from app.db.models.enums import CallOutcome, LeadStatus

_NOT_INTERESTED_RE = re.compile(
    r"\b(not interested|not now|no thanks|stop calling|do not want|don't want)\b",
    re.IGNORECASE,
)


class CallSummaryCreate(BaseModel):
    """Exactly the fields stored in ``call_summaries`` — all required."""

    summary: str = Field(min_length=1)
    key_requirements: list[str]
    customer_intent: str = Field(min_length=1)
    important_points: list[str]
    followup_actions: list[str]
    outcome: CallOutcome
    lead_status: LeadStatus
    followup_required: bool


def _label(slot: str) -> str:
    return slot.replace("_", " ")


def build_rule_based_summary(
    slots: dict[str, str | None],
    transcript: list[str],
    *,
    not_interested: bool | None = None,
) -> CallSummaryCreate:
    """Deterministic summary built purely from slots + transcript.

    Works with zero LLM availability — this is the guaranteed fallback.
    """
    filled = {k: v for k, v in (slots or {}).items() if v}
    text = "\n".join(transcript or [])
    if not_interested is None:
        not_interested = bool(_NOT_INTERESTED_RE.search(text))

    name = filled.get("customer_name")
    requirement = filled.get("requirement")
    capacity = filled.get("capacity")
    location = filled.get("location")
    budget = filled.get("budget")
    timeline = filled.get("timeline")
    application = filled.get("application")

    key_requirements = [
        f"{_label(slot)}: {filled[slot]}"
        for slot in (
            "requirement",
            "capacity",
            "location",
            "budget",
            "timeline",
            "customer_name",
        )
        if filled.get(slot)
    ]

    if not_interested:
        summary_sentence = (
            f"{name or 'The customer'} was not interested in the offer and asked not to "
            "be called again."
        )
        intent = "Not interested in purchasing right now."
        outcome = CallOutcome.not_interested
        lead_status = LeadStatus.not_interested
        followup_required = False
        actions: list[str] = []
        points = ["Opted out of further calls"]
    else:
        parts = [
            f"{name or 'The customer'} is looking for {requirement or 'a water treatment system'}"
        ]
        if capacity:
            parts.append(f"capacity {capacity}")
        if location:
            parts.append(f"to be installed in {location}")
        if budget:
            parts.append(f"budget {budget}")
        if timeline:
            parts.append(f"needed {timeline}")
        summary_sentence = "; ".join(parts) + "."
        intent = f"Wants to purchase {requirement or 'a commercial RO system'}"
        if timeline:
            intent += f" {timeline[0].lower() + timeline[1:]}"
        intent += "."
        complete = all(filled.get(s) for s in ("capacity", "location", "budget", "timeline"))
        outcome = CallOutcome.interested
        lead_status = LeadStatus.hot if complete else LeadStatus.warm
        followup_required = True
        actions = ["Share product quotation and specifications"]
        if timeline:
            actions.append(f"Follow up {timeline}")
        else:
            actions.append("Follow up with the customer")
        points = []
        if application:
            points.append(f"Application: {application}")
        if location:
            points.append(f"Site location: {location}")
        if budget:
            points.append(f"Budget mentioned: {budget}")
        if timeline:
            points.append(f"Required {timeline}")

    return CallSummaryCreate(
        summary=summary_sentence,
        key_requirements=key_requirements,
        customer_intent=intent,
        important_points=points,
        followup_actions=actions,
        outcome=outcome,
        lead_status=lead_status,
        followup_required=followup_required,
    )


def _llm_prompt(slots: dict[str, str | None], transcript: list[str]) -> str:
    slots_json = json.dumps(
        {k: v for k, v in (slots or {}).items() if v}, indent=2, ensure_ascii=False
    )
    convo = "\n".join(transcript or [])
    return (
        "You are summarising an outbound sales phone call for commercial RO systems.\n"
        "Return ONLY a JSON object with EXACTLY these keys:\n"
        '  "summary" (string), "key_requirements" (array of strings),\n'
        '  "customer_intent" (string), "important_points" (array of strings),\n'
        '  "followup_actions" (array of strings),\n'
        '  "outcome" (one of: interested, not_interested, callback_requested, no_response, failed, incomplete),\n'
        '  "lead_status" (one of: hot, warm, cold, interested, not_interested, unknown),\n'
        '  "followup_required" (boolean).\n'
        "No markdown, no commentary.\n\n"
        f"Collected slots:\n{slots_json}\n\nTranscript:\n{convo}\n"
    )


async def generate_summary(
    llm: LLMClient | None,
    slots: dict[str, str | None],
    transcript: list[str],
    *,
    not_interested: bool | None = None,
) -> tuple[CallSummaryCreate, str]:
    """Return ``(validated_summary, source)`` where source is llm|rule_based.

    LLM path: chat_json (internal retries) → Pydantic validation. Any failure
    at all falls through to the deterministic builder — never raises.
    """
    if llm is not None and llm.available:
        try:
            raw: dict[str, Any] = await llm.chat_json(_llm_prompt(slots, transcript))
            data = CallSummaryCreate.model_validate(raw)
            return data, "llm"
        except Exception:  # noqa: BLE001 — summary generation must never fail a call
            pass
    return (
        build_rule_based_summary(slots, transcript, not_interested=not_interested),
        "rule_based",
    )


__all__ = [
    "CallSummaryCreate",
    "build_rule_based_summary",
    "generate_summary",
]
