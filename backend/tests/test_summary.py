"""Post-call summary contract (D18) + persistence via summary_service."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from app.agent.summary import CallSummaryCreate, build_rule_based_summary
from app.db.models.enums import CallOutcome, LeadStatus
from app.services.summary_service import generate_and_store_summary
from pydantic import ValidationError

from tests.test_calls import _insert_call

CONTRACT_FIELDS = {
    "summary",
    "key_requirements",
    "customer_intent",
    "important_points",
    "followup_actions",
    "outcome",
    "lead_status",
    "followup_required",
}

FULL_SCRIPT_SLOTS = {
    "requirement": "a commercial RO system for my hotel",
    "capacity": "500 LPH",
    "location": "Bangalore",
    "budget": "around 1 lakh",
    "timeline": "within a month",
    "customer_name": "Rahul Kumar",
    "company": None,
    "application": "hotel",
    "additional_requirements": None,
}


# ── contract (D18) ────────────────────────────────────────────────────────────
def test_rule_based_summary_has_exactly_the_contract_fields() -> None:
    data = build_rule_based_summary(FULL_SCRIPT_SLOTS, [])
    assert set(data.model_dump()) == CONTRACT_FIELDS
    # and it round-trips through Pydantic validation
    CallSummaryCreate.model_validate(data.model_dump())


def test_rule_based_summary_contents_are_specific() -> None:
    data = build_rule_based_summary(FULL_SCRIPT_SLOTS, [])
    assert "500 LPH" in json.dumps(data.key_requirements)
    assert "Bangalore" in json.dumps(data.important_points)
    assert data.outcome == CallOutcome.interested
    assert data.lead_status == LeadStatus.hot
    assert data.followup_required is True
    assert data.followup_actions


def test_partial_slots_yield_warm_lead() -> None:
    partial = {**FULL_SCRIPT_SLOTS, "timeline": None}
    data = build_rule_based_summary(partial, [])
    assert data.lead_status == LeadStatus.warm
    assert data.outcome == CallOutcome.interested
    assert data.followup_required is True


def test_not_interested_transcript_marks_outcome() -> None:
    transcript = [
        "customer: I'm not interested, thanks",
        "agent: Understood, thanks for your time.",
    ]
    data = build_rule_based_summary({"customer_name": "Rahul Kumar"}, transcript)
    assert data.outcome == CallOutcome.not_interested
    assert data.lead_status == LeadStatus.not_interested
    assert data.followup_required is False
    assert data.followup_actions == []


def test_not_interested_flag_overrides_transcript() -> None:
    data = build_rule_based_summary(FULL_SCRIPT_SLOTS, ["customer: sure"], not_interested=True)
    assert data.outcome == CallOutcome.not_interested
    assert data.followup_required is False


def test_empty_everything_still_validates() -> None:
    data = build_rule_based_summary({}, [])
    CallSummaryCreate.model_validate(data.model_dump())
    assert set(data.model_dump()) == CONTRACT_FIELDS


def test_missing_field_is_rejected_by_pydantic() -> None:
    payload = build_rule_based_summary(FULL_SCRIPT_SLOTS, []).model_dump()
    payload.pop("followup_actions")
    with pytest.raises(ValidationError):
        CallSummaryCreate.model_validate(payload)


# ── persistence via summary_service ───────────────────────────────────────────
@pytest.mark.asyncio
async def test_generate_and_store_summary_writes_rows(client, auth_headers, db) -> None:
    from app.db.models.call_extracted_data import CallExtractedData
    from app.db.models.call_turn import CallTurn
    from app.db.models.enums import CallStatus, Speaker

    call = await _insert_call(db, status=CallStatus.completed, phone_number="+919876543210")
    async with db() as session:
        session.add(
            CallExtractedData(
                call_id=call.id,
                customer_name="Rahul Kumar",
                requirement="a commercial RO system for my hotel",
                ro_capacity_lph="500 LPH",
                location="Bangalore",
                budget="around 1 lakh",
                timeline="within a month",
                application="hotel",
            )
        )
        session.add(
            CallTurn(
                call_id=call.id,
                turn_index=0,
                speaker=Speaker.customer,
                message="I need a commercial RO system for my hotel",
                created_at=datetime.now(tz=UTC),
            )
        )
        session.add(
            CallTurn(
                call_id=call.id,
                turn_index=1,
                speaker=Speaker.agent,
                message="And what capacity do you need for the hotel?",
                created_at=datetime.now(tz=UTC),
            )
        )
        await session.commit()

    async with db() as session:
        summary = await generate_and_store_summary(session, call.id)
        await session.commit()

    assert summary is not None
    assert summary.outcome == CallOutcome.interested
    assert summary.lead_status == LeadStatus.hot
    assert summary.followup_required is True

    # visible through the API too (check C12 path)
    detail = await client.get(f"/calls/{call.id}", headers=auth_headers)
    assert detail.status_code == 200
    body = detail.json()
    assert set(body["summary"]) >= CONTRACT_FIELDS
    assert body["outcome"] == "interested"
    assert body["lead_status"] == "hot"
    assert body["turns"]  # transcript still there


@pytest.mark.asyncio
async def test_generate_and_store_summary_unknown_call_is_none(db) -> None:
    import uuid as uuid_mod

    async with db() as session:
        assert await generate_and_store_summary(session, uuid_mod.uuid4()) is None
