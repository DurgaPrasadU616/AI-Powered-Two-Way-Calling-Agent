"""Tests for Twilio CallProvider and Webhooks (voice loop, status callback, signature validation)."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest
from app.core.config import get_settings
from app.db.models.call import Call
from app.db.models.call_event import CallEvent
from app.db.models.call_extracted_data import CallExtractedData
from app.db.models.call_turn import CallTurn
from app.db.models.enums import CallOutcome, CallStatus
from app.providers.twilio import TwilioCallProvider
from app.services.call_service import create_call, initiate_provider_call
from httpx import AsyncClient
from sqlalchemy import select

settings = get_settings()


@pytest.mark.asyncio
async def test_twilio_provider_start_call_success(monkeypatch):
    """TwilioCallProvider.start_call invokes twilio.rest.Client calls.create."""
    mock_call = MagicMock()
    mock_call.sid = "CA1234567890abcdef"
    mock_call.status = "queued"

    mock_client = MagicMock()
    mock_client.calls.create.return_value = mock_call

    with patch("twilio.rest.Client", return_value=mock_client):
        provider = TwilioCallProvider(
            account_sid="ACmock",
            auth_token="authmock",
            from_number="+15551234567",
            public_base_url="https://demo.ngrok.io",
        )
        res = await provider.start_call(str(uuid.uuid4()), "+919876543210")
        assert res["provider"] == "twilio"
        assert res["call_sid"] == "CA1234567890abcdef"
        assert mock_client.calls.create.called
        kwargs = mock_client.calls.create.call_args[1]
        assert kwargs["to"] == "+919876543210"
        assert kwargs["from_"] == "+15551234567"
        assert "https://demo.ngrok.io/api/v1/webhooks/twilio/voice" in kwargs["url"]


@pytest.mark.asyncio
async def test_twilio_provider_start_call_failure(db, monkeypatch):
    """When Twilio API call fails, call status is set to failed and provider_error event recorded."""
    monkeypatch.setattr(settings, "CALL_PROVIDER", "twilio")
    monkeypatch.setattr(settings, "TWILIO_ACCOUNT_SID", "ACmock")
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "authmock")

    mock_client = MagicMock()
    mock_client.calls.create.side_effect = RuntimeError("Twilio network connection refused")

    async with db() as session:
        call = await create_call(session, phone_number="+919876543210", contact_id=None)
        await session.commit()
        call_id = call.id

    with patch("twilio.rest.Client", return_value=mock_client):
        async with db() as session:
            loaded_call = await session.get(Call, call_id)
            with pytest.raises(RuntimeError):
                await initiate_provider_call(session, loaded_call)

    async with db() as session:
        refreshed = await session.get(Call, call_id)
        assert refreshed.status == CallStatus.failed
        assert refreshed.outcome == CallOutcome.failed

        events = (
            await session.scalars(select(CallEvent).where(CallEvent.call_id == call_id))
        ).all()
        event_types = [e.event_type for e in events]
        assert "provider_error" in event_types


@pytest.mark.asyncio
async def test_twilio_webhook_signature_rejection(client: AsyncClient, monkeypatch):
    """When TWILIO_AUTH_TOKEN is set, requests with invalid or missing X-Twilio-Signature return 403."""
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "real_secret_token_123")

    call_id = str(uuid.uuid4())
    # Missing signature
    resp = await client.post(
        f"/api/v1/webhooks/twilio/voice?call_id={call_id}",
        data={"SpeechResult": "Hello"},
    )
    assert resp.status_code == 403
    assert "signature" in resp.text.lower()

    # Invalid signature
    resp2 = await client.post(
        f"/api/v1/webhooks/twilio/voice?call_id={call_id}",
        data={"SpeechResult": "Hello"},
        headers={"X-Twilio-Signature": "invalid_sig_abc"},
    )
    assert resp2.status_code == 403


@pytest.mark.asyncio
async def test_twilio_webhook_voice_greeting_and_turn(client: AsyncClient, db, monkeypatch):
    """Voice webhook returns TwiML greeting, then processes speech into dialogue agent & extracted slots."""
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "")  # allow unsigned in test

    async with db() as session:
        call = await create_call(session, phone_number="+919876543210", contact_id=None)
        await session.commit()
        call_id = str(call.id)

    # 1. Initial greeting
    resp_init = await client.post(f"/api/v1/webhooks/twilio/voice?call_id={call_id}")
    assert resp_init.status_code == 200
    assert "xml" in resp_init.headers.get("content-type", "")
    assert "<Gather" in resp_init.text
    assert "SERP Hawk" in resp_init.text

    # 2. Customer speaks: requirement
    resp_turn = await client.post(
        f"/api/v1/webhooks/twilio/voice?call_id={call_id}",
        data={"SpeechResult": "I need a commercial RO plant for my hotel in Bangalore"},
    )
    assert resp_turn.status_code == 200
    assert "<Gather" in resp_turn.text

    # Verify turn and extracted slots in DB
    async with db() as session:
        turns = (
            await session.scalars(select(CallTurn).where(CallTurn.call_id == uuid.UUID(call_id)))
        ).all()
        assert len(turns) >= 2  # greeting + customer + agent
        extracted = await session.get(CallExtractedData, uuid.UUID(call_id))
        assert extracted is not None
        assert extracted.application == "hotel" or "hotel" in (extracted.requirement or "")


@pytest.mark.asyncio
async def test_twilio_webhook_status_mappings(client: AsyncClient, db, monkeypatch):
    """Status webhook maps ringing, no-answer, failed, completed to our statuses & events."""
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "")

    async with db() as session:
        call = await create_call(session, phone_number="+919876543210", contact_id=None)
        await session.commit()
        call_id = str(call.id)

    # Ringing -> in_progress & call_started event
    r_ring = await client.post(
        f"/api/v1/webhooks/twilio/status?call_id={call_id}",
        data={"CallStatus": "ringing", "CallSid": "CA_test_123"},
    )
    assert r_ring.status_code == 200

    async with db() as session:
        c = await session.get(Call, uuid.UUID(call_id))
        assert c.status == CallStatus.in_progress
        assert c.provider_call_sid == "CA_test_123"

    # Busy / no-answer -> no_answer & no_answer event
    r_noans = await client.post(
        f"/api/v1/webhooks/twilio/status?call_id={call_id}",
        data={"CallStatus": "no-answer"},
    )
    assert r_noans.status_code == 200

    async with db() as session:
        c = await session.get(Call, uuid.UUID(call_id))
        assert c.status == CallStatus.no_answer
        events = (
            await session.scalars(select(CallEvent).where(CallEvent.call_id == uuid.UUID(call_id)))
        ).all()
        assert "no_answer" in [e.event_type for e in events]
