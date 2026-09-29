"""Phase 4 realtime tests — WS call flow, silence timeout, drop, guards.

The LLM is mocked (5 scripted replies); everything else is real: dialogue
state machine, persistence, summary generation — all against the test DB.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from app.core.security import create_access_token
from app.db.models.call import Call
from app.db.models.call_event import CallEvent
from app.db.models.call_extracted_data import CallExtractedData
from app.db.models.call_summary import CallSummary
from app.db.models.call_turn import CallTurn
from app.db.models.enums import CallStatus, LeadStatus, Speaker
from app.main import app
from app.realtime import call_session as call_session_module
from sqlalchemy import select
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

_TOKEN = create_access_token("admin@sephawk.com")


# ── helpers ────────────────────────────────────────────────────────────────────
class _FakeLLM:
    """Mocked LLM: available, deterministic scripted replies."""

    available = True

    def __init__(self, replies: list[str]) -> None:
        self.chat = AsyncMock(side_effect=replies)


_SCRIPTED_REPLIES = [
    "Great, what capacity do you need for the hotel?",
    "Thanks, and where should we install it?",
    "Understood. And what budget did you have in mind?",
    "Noted. By when do you need it?",
    "Thank you. May I know your name?",
]

_SCRIPTED_UTTERANCES = [
    "I need a 1000 lph RO system for my hotel",
    "500 lph is fine",
    "Pune",
    "Around 5 lakhs",
    "Within a month",
    "My name is Rahul Kumar",
]


async def _make_call(db) -> uuid.UUID:
    async with db() as session:
        call = Call(
            phone_number="+919876543210",
            status=CallStatus.queued,
            lead_status=LeadStatus.unknown,
            followup_required=False,
            created_at=datetime.now(tz=UTC),
        )
        session.add(call)
        await session.commit()
        return call.id


def _install_fake_llm(monkeypatch, replies=None) -> _FakeLLM:
    fake = _FakeLLM(list(replies if replies is not None else _SCRIPTED_REPLIES))
    monkeypatch.setattr(call_session_module, "get_llm", lambda: fake)
    monkeypatch.setattr("app.services.summary_service.get_llm", lambda: fake)
    monkeypatch.setattr("app.agent.llm.get_llm", lambda: fake)
    return fake


# ── full conversation over the socket ─────────────────────────────────────────
async def test_ws_full_conversation_persists_everything(db, monkeypatch) -> None:
    call_id = await _make_call(db)
    fake = _install_fake_llm(monkeypatch)

    with (
        TestClient(app) as http,
        http.websocket_connect(f"/ws/call/{call_id}?token={_TOKEN}") as ws,
    ):
        opening = ws.receive_json()
        assert opening["type"] == "agent_reply"
        assert "Hello, this is the assistant calling from SERP Hawk" in opening["text"]
        state = ws.receive_json()
        assert state["type"] == "state_update"
        assert state["phase"] == "GATHERING"

        for i, text in enumerate(_SCRIPTED_UTTERANCES):
            ws.send_json({"type": "customer_speech", "text": text, "confidence": 0.97})
            reply = ws.receive_json()
            assert reply["type"] == "agent_reply"
            assert reply["turn_index"] == 2 * i + 2
            state = ws.receive_json()
            assert state["type"] == "state_update"
            if i == 0:
                # barge-in mid-call: server logs the event, sends nothing back
                ws.send_json({"type": "interrupt"})
            if i == len(_SCRIPTED_UTTERANCES) - 1:
                # WRAP_UP reached → call finishes
                status = ws.receive_json()
                assert status["type"] == "call_status"
                assert status["status"] == "completed"
                assert status["reason"] == "completed"
                assert status["duration_seconds"] >= 0

    # LLM used for the 5 gathering turns; the closing is deterministic
    assert fake.chat.await_count == 5

    async with db() as session:
        call = await session.get(Call, call_id)
        assert call.status == CallStatus.completed
        assert call.start_time is not None and call.end_time is not None
        assert call.duration_seconds is not None
        assert call.outcome is not None and call.lead_status is not None

        turns = (
            (await session.scalars(select(CallTurn).where(CallTurn.call_id == call_id)))
            .unique()
            .all()
        )
        speakers = [(t.turn_index, t.speaker) for t in sorted(turns, key=lambda t: t.turn_index)]
        # opening + 6 customer + 6 agent = 13 turns, strictly alternating
        assert len(turns) == 13
        assert speakers[0][1] == Speaker.agent
        for idx, (turn_index, speaker) in enumerate(speakers):
            assert turn_index == idx
            assert speaker == (Speaker.agent if idx % 2 == 0 else Speaker.customer)

        extracted = await session.get(CallExtractedData, call_id)
        assert extracted is not None
        assert extracted.customer_name == "Rahul Kumar"
        assert extracted.ro_capacity_lph is not None
        assert extracted.location == "Pune"
        assert extracted.requirement is not None

        summary = await session.get(CallSummary, call_id)
        assert summary is not None and summary.summary
        assert summary.followup_required in (True, False)

        events = (
            (await session.scalars(select(CallEvent).where(CallEvent.call_id == call_id)))
            .unique()
            .all()
        )
        types = {e.event_type for e in events}
        assert {"call_started", "call_ended", "interrupted"} <= types


# ── explicit End Call ──────────────────────────────────────────────────────────
async def test_ws_end_call_sends_status(db, monkeypatch) -> None:
    call_id = await _make_call(db)
    _install_fake_llm(monkeypatch, replies=["Sure, what are you looking for?"])

    with (
        TestClient(app) as http,
        http.websocket_connect(f"/ws/call/{call_id}?token={_TOKEN}") as ws,
    ):
        ws.receive_json()  # agent_reply opening
        ws.receive_json()  # state_update
        ws.send_json({"type": "end_call"})
        status = ws.receive_json()
        assert status == {
            "type": "call_status",
            "status": "completed",
            "reason": "completed",
            "duration_seconds": status["duration_seconds"],
        }

    async with db() as session:
        call = await session.get(Call, call_id)
        assert call.status == CallStatus.completed
        assert call.end_time is not None
        summary = await session.get(CallSummary, call_id)
        assert summary is not None  # partial transcript still summarized


# ── socket drop mid-call ───────────────────────────────────────────────────────
async def test_ws_disconnect_marks_disconnected_with_summary(db, monkeypatch) -> None:
    call_id = await _make_call(db)
    _install_fake_llm(monkeypatch, replies=["Sure, what are you looking for?"])

    with TestClient(app) as http:
        with http.websocket_connect(f"/ws/call/{call_id}?token={_TOKEN}") as ws:
            ws.receive_json()
            ws.receive_json()
            ws.send_json({"type": "customer_speech", "text": "I need an RO plant"})
            ws.receive_json()  # agent_reply
            ws.receive_json()  # state_update
        # client dropped — wait for server loop to finish disconnect processing
        for _ in range(30):
            await asyncio.sleep(0.1)
            async with db() as session:
                call = await session.get(Call, call_id)
                if call and call.status == CallStatus.disconnected:
                    break

    async with db() as session:
        call = await session.get(Call, call_id)
        assert call.status == CallStatus.disconnected
        assert call.end_time is not None
        summary = await session.get(CallSummary, call_id)
        assert summary is not None and summary.summary  # partial transcript summarized
        events = (
            (await session.scalars(select(CallEvent).where(CallEvent.call_id == call_id)))
            .unique()
            .all()
        )
        assert "disconnected" in {e.event_type for e in events}


# ── silence: prompt, prompt, silence_timeout ──────────────────────────────────
async def test_silence_prompts_then_times_out(db) -> None:
    from app.realtime.call_session import CallSession

    call_id = await _make_call(db)
    sent: list[dict] = []

    async def send(message: dict) -> None:
        sent.append(message)

    session = CallSession(call_id, db, send, silence_seconds=0.05, max_prompts=2)
    await session.start()
    await asyncio.sleep(0.45)  # 2 nudges at 0.05/0.10, timeout at 0.15

    nudges = [
        m for m in sent if m.get("type") == "agent_reply" and m["text"] == "Are you still there?"
    ]
    assert len(nudges) == 2
    statuses = [m for m in sent if m["type"] == "call_status"]
    assert len(statuses) == 1
    assert statuses[0]["reason"] == "silence_timeout"
    assert statuses[0]["status"] == "completed"

    async with db() as session2:
        call = await session2.get(Call, call_id)
        assert call.status == CallStatus.completed
        events = (
            (await session2.scalars(select(CallEvent).where(CallEvent.call_id == call_id)))
            .unique()
            .all()
        )
        assert "silence_timeout" in {e.event_type for e in events}
        turns = (
            (await session2.scalars(select(CallTurn).where(CallTurn.call_id == call_id)))
            .unique()
            .all()
        )
        # opening + 2 nudges
        assert len(turns) == 3
        assert all(t.speaker == Speaker.agent for t in turns)


# ── guard rails ────────────────────────────────────────────────────────────────
async def test_ws_unknown_call_returns_error(db) -> None:
    missing = uuid.uuid4()
    with (
        TestClient(app) as http,
        http.websocket_connect(f"/ws/call/{missing}?token={_TOKEN}") as ws,
    ):
        message = ws.receive_json()
        assert message == {"type": "error", "detail": "call not found"}


async def test_ws_invalid_call_id_returns_error(db) -> None:
    with (
        TestClient(app) as http,
        http.websocket_connect(f"/ws/call/not-a-uuid?token={_TOKEN}") as ws,
    ):
        message = ws.receive_json()
        assert message == {"type": "error", "detail": "invalid call id"}


async def test_ws_unknown_message_type_returns_error(db, monkeypatch) -> None:
    call_id = await _make_call(db)
    _install_fake_llm(monkeypatch, replies=["Sure, what are you looking for?"])
    with (
        TestClient(app) as http,
        http.websocket_connect(f"/ws/call/{call_id}?token={_TOKEN}") as ws,
    ):
        ws.receive_json()
        ws.receive_json()
        ws.send_json({"type": "teleport"})
        message = ws.receive_json()
        assert message["type"] == "error"
        assert "unknown message type" in message["detail"]


async def test_ws_cannot_reopen_finished_call(db, monkeypatch) -> None:
    call_id = await _make_call(db)
    _install_fake_llm(monkeypatch)
    with TestClient(app) as http:
        with http.websocket_connect(f"/ws/call/{call_id}?token={_TOKEN}") as ws:
            ws.receive_json()
            ws.receive_json()
            ws.send_json({"type": "end_call"})
            ws.receive_json()
        # second connection after the call ended
        with http.websocket_connect(f"/ws/call/{call_id}?token={_TOKEN}") as ws2:
            message = ws2.receive_json()
            assert message == {"type": "error", "detail": "call already ended"}


# ── WebSocket authentication tests ─────────────────────────────────────────────
async def test_ws_auth_rejected_without_token(db) -> None:
    call_id = await _make_call(db)
    with (
        TestClient(app) as http,
        pytest.raises(WebSocketDisconnect) as exc_info,
        http.websocket_connect(f"/ws/call/{call_id}"),
    ):
        pass
    assert exc_info.value.code == 1008


async def test_ws_auth_rejected_with_invalid_token(db) -> None:
    call_id = await _make_call(db)
    with (
        TestClient(app) as http,
        pytest.raises(WebSocketDisconnect) as exc_info,
        http.websocket_connect(f"/ws/call/{call_id}?token=invalid.jwt.token"),
    ):
        pass
    assert exc_info.value.code == 1008


async def test_ws_auth_accepted_with_valid_token(db) -> None:
    call_id = await _make_call(db)
    with (
        TestClient(app) as http,
        http.websocket_connect(f"/ws/call/{call_id}?token={_TOKEN}") as ws,
    ):
        opening = ws.receive_json()
        assert opening["type"] == "agent_reply"


async def test_ws_invalid_phone_records_invalid_number_status(db) -> None:
    async with db() as session:
        call = Call(
            phone_number="not-a-valid-phone",
            status=CallStatus.queued,
            lead_status=LeadStatus.unknown,
            followup_required=False,
        )
        session.add(call)
        await session.commit()
        call_id = call.id

    with (
        TestClient(app) as http,
        http.websocket_connect(f"/ws/call/{call_id}?token={_TOKEN}") as ws,
    ):
        status = ws.receive_json()
        assert status["type"] == "call_status"
        assert status["status"] == "invalid_number"

    async with db() as session:
        refreshed = await session.get(Call, call_id)
        assert refreshed.status == CallStatus.invalid_number
        events = (
            (await session.scalars(select(CallEvent).where(CallEvent.call_id == call_id)))
            .unique()
            .all()
        )
        assert "invalid_number" in {e.event_type for e in events}


async def test_ws_simulate_failure_paths(db, monkeypatch) -> None:
    from app.core.config import get_settings

    settings = get_settings()

    # 1. Provider failure simulation
    monkeypatch.setattr(settings, "SIMULATE_FAILURE", "provider")
    call_id = await _make_call(db)
    with (
        TestClient(app) as http,
        http.websocket_connect(f"/ws/call/{call_id}?token={_TOKEN}") as ws,
    ):
        err = ws.receive_json()
        assert err["type"] == "error"

    async with db() as session:
        events = (
            (await session.scalars(select(CallEvent).where(CallEvent.call_id == call_id)))
            .unique()
            .all()
        )
        assert "provider_error" in {e.event_type for e in events}

    # 2. STT and LLM failure simulation
    monkeypatch.setattr(settings, "SIMULATE_FAILURE", "stt")
    call_id2 = await _make_call(db)
    with (
        TestClient(app) as http,
        http.websocket_connect(f"/ws/call/{call_id2}?token={_TOKEN}") as ws2,
    ):
        ws2.receive_json()  # opening
        ws2.receive_json()  # state
        ws2.send_json({"type": "customer_speech", "text": "I need commercial RO"})
        ws2.receive_json()  # reply
        ws2.receive_json()  # state

    async with db() as session:
        events = (
            (await session.scalars(select(CallEvent).where(CallEvent.call_id == call_id2)))
            .unique()
            .all()
        )
        assert "stt_failure" in {e.event_type for e in events}
