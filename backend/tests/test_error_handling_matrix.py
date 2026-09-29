"""Dedicated tests proving the complete 8-case error handling matrix."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from starlette.testclient import TestClient

from app.core.config import get_settings
from app.core.security import create_access_token
from app.db.models.call import Call
from app.db.models.call_event import CallEvent
from app.db.models.enums import CallOutcome, CallStatus, LeadStatus
from app.main import app

settings = get_settings()
_TOKEN = create_access_token("admin@sephawk.com")


async def _seed_call(db, phone: str = "+919876543210") -> uuid.UUID:
    async with db() as session:
        call = Call(
            phone_number=phone,
            status=CallStatus.queued,
            lead_status=LeadStatus.unknown,
            followup_required=False,
            created_at=datetime.now(tz=UTC),
        )
        session.add(call)
        await session.commit()
        return call.id


@pytest.mark.asyncio
async def test_case_1_no_answer(client: AsyncClient, db, monkeypatch):
    """Case 1: No answer via status callback transitions to no_answer status & event."""
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "")
    call_id = await _seed_call(db)

    resp = await client.post(
        f"/api/v1/webhooks/twilio/status?call_id={call_id}",
        data={"CallStatus": "no-answer"},
    )
    assert resp.status_code == 200

    async with db() as session:
        call = await session.get(Call, call_id)
        assert call.status == CallStatus.no_answer
        assert call.outcome == CallOutcome.no_response
        events = (await session.scalars(select(CallEvent).where(CallEvent.call_id == call_id))).all()
        assert "no_answer" in [e.event_type for e in events]


@pytest.mark.asyncio
async def test_case_2_disconnect(db):
    """Case 2: Abrupt client disconnect transitions to disconnected status & event."""
    call_id = await _seed_call(db)

    with (
        TestClient(app) as http,
        http.websocket_connect(f"/ws/call/{call_id}?token={_TOKEN}") as ws,
    ):
        ws.receive_json()  # greeting
        # client abruptly closes connection without end_call
        ws.close()

    async with db() as session:
        call = await session.get(Call, call_id)
        assert call.status == CallStatus.disconnected
        events = (await session.scalars(select(CallEvent).where(CallEvent.call_id == call_id))).all()
        assert "disconnected" in [e.event_type for e in events]


@pytest.mark.asyncio
async def test_case_3_stt_failure(db):
    """Case 3: Browser STT failure diagnostic message logs stt_failure event while call stays in progress."""
    call_id = await _seed_call(db)

    with (
        TestClient(app) as http,
        http.websocket_connect(f"/ws/call/{call_id}?token={_TOKEN}") as ws,
    ):
        ws.receive_json()  # greeting
        ws.receive_json()  # state
        ws.send_json({"type": "stt_failure", "detail": {"error": "audio-capture"}})
        # call continues
        ws.send_json({"type": "customer_speech", "text": "I need commercial RO system"})
        reply = ws.receive_json()
        assert reply["type"] == "agent_reply"

    async with db() as session:
        call = await session.get(Call, call_id)
        events = (await session.scalars(select(CallEvent).where(CallEvent.call_id == call_id))).all()
        assert "stt_failure" in [e.event_type for e in events]


@pytest.mark.asyncio
async def test_case_4_llm_failure(db, monkeypatch):
    """Case 4: LLM failure logs llm_failure event and transparently falls back to deterministic reply."""
    monkeypatch.setattr(settings, "SIMULATE_FAILURE", "llm")
    call_id = await _seed_call(db)

    with (
        TestClient(app) as http,
        http.websocket_connect(f"/ws/call/{call_id}?token={_TOKEN}") as ws,
    ):
        ws.receive_json()  # greeting
        ws.receive_json()  # state
        ws.send_json({"type": "customer_speech", "text": "I need 500 LPH RO system for hotel"})
        reply = ws.receive_json()
        assert reply["type"] == "agent_reply"
        assert len(reply["text"]) > 0

    async with db() as session:
        events = (await session.scalars(select(CallEvent).where(CallEvent.call_id == call_id))).all()
        assert "llm_failure" in [e.event_type for e in events]


@pytest.mark.asyncio
async def test_case_5_invalid_phone(client: AsyncClient, db):
    """Case 5: Invalid phone number is rejected at schema level or marks invalid_number status."""
    call_id = await _seed_call(db, phone="invalid_number_123")

    with (
        TestClient(app) as http,
        http.websocket_connect(f"/ws/call/{call_id}?token={_TOKEN}") as ws,
    ):
        status = ws.receive_json()
        assert status["status"] == "invalid_number"

    async with db() as session:
        call = await session.get(Call, call_id)
        assert call.status == CallStatus.invalid_number
        events = (await session.scalars(select(CallEvent).where(CallEvent.call_id == call_id))).all()
        assert "invalid_number" in [e.event_type for e in events]


@pytest.mark.asyncio
async def test_case_6_provider_failure(db, monkeypatch):
    """Case 6: Telephony provider failure sets failed status and records provider_error."""
    monkeypatch.setattr(settings, "SIMULATE_FAILURE", "provider")
    call_id = await _seed_call(db)

    with (
        TestClient(app) as http,
        http.websocket_connect(f"/ws/call/{call_id}?token={_TOKEN}") as ws,
    ):
        msg = ws.receive_json()
        assert msg["type"] == "error"

    async with db() as session:
        events = (await session.scalars(select(CallEvent).where(CallEvent.call_id == call_id))).all()
        assert "provider_error" in [e.event_type for e in events]


@pytest.mark.asyncio
async def test_case_7_silence_timeout(db):
    """Case 7: Sustained silence nudges twice then terminates with silence_timeout event."""
    from app.realtime.call_session import CallSession

    async with db() as session:
        call_id = await _seed_call(db)

    sent = []

    async def _mock_send(msg):
        sent.append(msg)

    cs = CallSession(
        call_id=call_id,
        session_factory=db,
        send=_mock_send,
        silence_seconds=0.05,
        max_prompts=2,
    )
    await cs.start()
    # Wait for silence loop to fire prompts and terminate
    await asyncio.sleep(0.3)

    async with db() as session:
        call = await session.get(Call, call_id)
        assert call.status == CallStatus.completed
        events = (await session.scalars(select(CallEvent).where(CallEvent.call_id == call_id))).all()
        assert "silence_timeout" in [e.event_type for e in events]


@pytest.mark.asyncio
async def test_case_8_interruption(db):
    """Case 8: Customer barge-in emits interrupt signal and records interrupted event."""
    call_id = await _seed_call(db)

    with (
        TestClient(app) as http,
        http.websocket_connect(f"/ws/call/{call_id}?token={_TOKEN}") as ws,
    ):
        ws.receive_json()  # greeting
        ws.receive_json()  # state
        ws.send_json({"type": "interrupt"})
        # Call stays in progress
        ws.send_json({"type": "customer_speech", "text": "Excuse me, I need commercial RO"})
        reply = ws.receive_json()
        assert reply["type"] == "agent_reply"

    async with db() as session:
        events = (await session.scalars(select(CallEvent).where(CallEvent.call_id == call_id))).all()
        assert "interrupted" in [e.event_type for e in events]
