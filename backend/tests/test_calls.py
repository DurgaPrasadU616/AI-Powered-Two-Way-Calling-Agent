"""Phase 2 call tests — create/end, every list filter, pagination, detail."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from app.db.models.call import Call
from app.db.models.call_event import CallEvent
from app.db.models.call_extracted_data import CallExtractedData
from app.db.models.call_summary import CallSummary
from app.db.models.call_turn import CallTurn
from app.db.models.enums import CallOutcome, CallStatus, LeadStatus, Speaker
from httpx import AsyncClient
from sqlalchemy import select


async def _insert_call(db, **fields) -> Call:
    defaults = {
        "phone_number": "+919876543210",
        "status": CallStatus.queued,
        "lead_status": LeadStatus.unknown,
        "followup_required": False,
        "created_at": datetime.now(tz=UTC),
    }
    defaults.update(fields)
    async with db() as session:
        call = Call(**defaults)
        session.add(call)
        await session.commit()
        await session.refresh(call)
        return call


# ── create / end ──────────────────────────────────────────────────────────────
async def test_create_call_is_queued(client: AsyncClient, auth_headers: dict) -> None:
    response = await client.post(
        "/calls", json={"phone_number": "+919876543210"}, headers=auth_headers
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "queued"
    assert body["outcome"] is None
    assert body["lead_status"] == "unknown"
    uuid.UUID(body["id"])  # valid UUID


async def test_create_call_from_contact_uses_contact_phone(
    client: AsyncClient, auth_headers: dict, make_contact
) -> None:
    contact = await make_contact(name="Rahul", phone="+919876543210")
    response = await client.post("/calls", json={"contact_id": contact["id"]}, headers=auth_headers)
    assert response.status_code == 201, response.text
    assert response.json()["phone_number"] == "+919876543210"


async def test_create_call_with_invalid_phone_422(client: AsyncClient, auth_headers: dict) -> None:
    response = await client.post("/calls", json={"phone_number": "12345"}, headers=auth_headers)
    assert response.status_code == 422


async def test_create_call_without_number_or_contact_422(
    client: AsyncClient, auth_headers: dict
) -> None:
    response = await client.post("/calls", json={}, headers=auth_headers)
    assert response.status_code == 422


async def test_end_call_sets_completed_and_duration(
    client: AsyncClient, auth_headers: dict, db
) -> None:
    call = await _insert_call(
        db,
        status=CallStatus.in_progress,
        start_time=datetime.now(tz=UTC) - timedelta(seconds=42),
    )
    response = await client.post(f"/calls/{call.id}/end", headers=auth_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "completed"
    assert body["end_time"] is not None
    assert body["duration_seconds"] >= 42

    # ending again is a no-op (no double-counting)
    again = await client.post(f"/calls/{call.id}/end", headers=auth_headers)
    assert again.status_code == 200
    assert again.json()["duration_seconds"] == body["duration_seconds"]


async def test_end_unknown_call_404(client: AsyncClient, auth_headers: dict) -> None:
    response = await client.post(f"/calls/{uuid.uuid4()}/end", headers=auth_headers)
    assert response.status_code == 404


# ── filters ───────────────────────────────────────────────────────────────────
async def test_filter_by_status(client: AsyncClient, auth_headers: dict, db) -> None:
    await _insert_call(db, status=CallStatus.queued)
    await _insert_call(db, status=CallStatus.completed)
    response = await client.get("/calls", params={"status": "completed"}, headers=auth_headers)
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["status"] == "completed"


async def test_filter_by_lead_status(client: AsyncClient, auth_headers: dict, db) -> None:
    await _insert_call(db, lead_status=LeadStatus.hot)
    await _insert_call(db, lead_status=LeadStatus.cold)
    response = await client.get("/calls", params={"lead_status": "hot"}, headers=auth_headers)
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["lead_status"] == "hot"


async def test_filter_by_followup_required(client: AsyncClient, auth_headers: dict, db) -> None:
    await _insert_call(db, followup_required=True)
    await _insert_call(db, followup_required=False)
    response = await client.get(
        "/calls", params={"followup_required": "true"}, headers=auth_headers
    )
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["followup_required"] is True

    none_of_them = await client.get(
        "/calls", params={"followup_required": "false"}, headers=auth_headers
    )
    assert len(none_of_them.json()["items"]) == 1


async def test_filter_by_outcome(client: AsyncClient, auth_headers: dict, db) -> None:
    await _insert_call(db, outcome=CallOutcome.interested, status=CallStatus.completed)
    await _insert_call(db, outcome=CallOutcome.not_interested, status=CallStatus.completed)
    response = await client.get("/calls", params={"outcome": "interested"}, headers=auth_headers)
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["outcome"] == "interested"


async def test_filter_by_date_range(client: AsyncClient, auth_headers: dict, db) -> None:
    today = datetime.now(tz=UTC)
    await _insert_call(db, created_at=today)
    await _insert_call(db, created_at=today - timedelta(days=3))

    in_range = await client.get(
        "/calls",
        params={
            "date_from": (today - timedelta(days=1)).date().isoformat(),
            "date_to": today.date().isoformat(),
        },
        headers=auth_headers,
    )
    assert in_range.status_code == 200
    assert len(in_range.json()["items"]) == 1

    wider = await client.get(
        "/calls",
        params={
            "date_from": (today - timedelta(days=7)).date().isoformat(),
            "date_to": today.date().isoformat(),
        },
        headers=auth_headers,
    )
    assert len(wider.json()["items"]) == 2


async def test_filter_by_customer_id_and_name(
    client: AsyncClient, auth_headers: dict, db, make_contact
) -> None:
    rahul = await make_contact(name="Rahul Kumar", phone="+919876543210")
    priya = await make_contact(name="Priya Sharma", phone="+919845123456")
    await _insert_call(db, contact_id=rahul["id"], phone_number="+919876543210")
    await _insert_call(db, contact_id=priya["id"], phone_number="+919845123456")
    await _insert_call(db)  # no contact

    by_id = await client.get("/calls", params={"customer": str(rahul["id"])}, headers=auth_headers)
    assert len(by_id.json()["items"]) == 1
    assert by_id.json()["items"][0]["contact_id"] == rahul["id"]

    by_name = await client.get("/calls", params={"customer": "priya"}, headers=auth_headers)
    assert len(by_name.json()["items"]) == 1
    assert by_name.json()["items"][0]["contact_id"] == priya["id"]


async def test_pagination_meta(client: AsyncClient, auth_headers: dict, db) -> None:
    base = datetime.now(tz=UTC)
    for i in range(5):
        await _insert_call(db, created_at=base - timedelta(minutes=i))

    page1 = await client.get("/calls", params={"page": 1, "page_size": 2}, headers=auth_headers)
    assert page1.status_code == 200
    body = page1.json()
    assert len(body["items"]) == 2
    assert body["meta"] == {"page": 1, "page_size": 2, "total": 5, "pages": 3}

    page3 = await client.get("/calls", params={"page": 3, "page_size": 2}, headers=auth_headers)
    assert len(page3.json()["items"]) == 1
    assert page3.json()["meta"]["page"] == 3


async def test_invalid_enum_filter_is_422(client: AsyncClient, auth_headers: dict) -> None:
    response = await client.get("/calls", params={"status": "not-a-status"}, headers=auth_headers)
    assert response.status_code == 422


# ── detail ────────────────────────────────────────────────────────────────────
async def test_call_detail_includes_all_sections(
    client: AsyncClient, auth_headers: dict, db, make_contact
) -> None:
    contact = await make_contact(name="Rahul Kumar")
    call = await _insert_call(db, contact_id=contact["id"], status=CallStatus.completed)
    async with db() as session:
        session.add(
            CallTurn(call_id=call.id, turn_index=0, speaker=Speaker.agent, message="Hello!")
        )
        session.add(CallTurn(call_id=call.id, turn_index=1, speaker=Speaker.customer, message="Hi"))
        session.add(
            CallExtractedData(call_id=call.id, customer_name="Rahul Kumar", location="Bangalore")
        )
        session.add(
            CallSummary(
                call_id=call.id,
                summary="Interested in a 500 LPH RO for a hotel.",
                key_requirements={"capacity": "500 LPH"},
                customer_intent="buying",
                important_points=["Bangalore"],
                followup_actions=["send quote"],
                outcome=CallOutcome.interested,
                lead_status=LeadStatus.hot,
                followup_required=True,
            )
        )
        session.add(CallEvent(call_id=call.id, event_type="call_started"))
        await session.commit()

    response = await client.get(f"/calls/{call.id}", headers=auth_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["contact_name"] == "Rahul Kumar"
    assert [t["turn_index"] for t in body["turns"]] == [0, 1]
    assert body["turns"][0]["speaker"] == "agent"
    assert body["extracted_data"]["customer_name"] == "Rahul Kumar"
    assert body["summary"]["followup_required"] is True
    assert body["summary"]["key_requirements"] == {"capacity": "500 LPH"}
    assert [e["event_type"] for e in body["events"]] == ["call_started"]


async def test_call_detail_404(client: AsyncClient, auth_headers: dict) -> None:
    response = await client.get(f"/calls/{uuid.uuid4()}", headers=auth_headers)
    assert response.status_code == 404


async def test_calls_require_auth(client: AsyncClient) -> None:
    response = await client.get("/calls")
    assert response.status_code == 401


async def test_call_created_event_logged(client: AsyncClient, auth_headers: dict, db) -> None:
    created = await client.post(
        "/calls", json={"phone_number": "+919876543210"}, headers=auth_headers
    )
    call_id = uuid.UUID(created.json()["id"])
    async with db() as session:
        events = list(
            (await session.scalars(select(CallEvent).where(CallEvent.call_id == call_id))).all()
        )
    assert [e.event_type for e in events] == ["call_created"]


async def test_patch_call_metadata(client: AsyncClient, auth_headers: dict, db) -> None:
    created = await client.post(
        "/calls", json={"phone_number": "+919876543210"}, headers=auth_headers
    )
    call_id = created.json()["id"]

    # PATCH lead_status and followup_required
    patch_res = await client.patch(
        f"/calls/{call_id}",
        json={"lead_status": "hot", "followup_required": True, "outcome": "interested"},
        headers=auth_headers,
    )
    assert patch_res.status_code == 200
    data = patch_res.json()
    assert data["lead_status"] == "hot"
    assert data["followup_required"] is True
    assert data["outcome"] == "interested"

    # Verify detail reflects updated state
    detail_res = await client.get(f"/calls/{call_id}", headers=auth_headers)
    assert detail_res.status_code == 200
    assert detail_res.json()["lead_status"] == "hot"
