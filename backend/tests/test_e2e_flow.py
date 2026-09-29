"""End-to-End Verification Test for the complete sales call flow."""

from __future__ import annotations

from app.main import app
from httpx import AsyncClient
from starlette.testclient import TestClient

from tests.test_ws import _install_fake_llm


async def test_full_e2e_sales_call_flow(
    client: AsyncClient, auth_headers: dict, db, monkeypatch
) -> None:
    # 1. Verify Initial Dashboard Stats
    resp = await client.get("/dashboard/stats", headers=auth_headers)
    assert resp.status_code == 200
    stats_before = resp.json()

    # 2. Add Contact
    contact_payload = {
        "name": "Ramesh Patel",
        "phone_e164": "+919876543210",
        "company": "Grand Orchid Hotel",
        "purpose": "Commercial RO System",
        "product": "500 LPH Industrial RO",
    }
    resp = await client.post("/contacts", json=contact_payload, headers=auth_headers)
    assert resp.status_code == 201
    contact = resp.json()
    contact_id = contact["id"]

    # 3. Start Call
    resp = await client.post("/calls", json={"contact_id": contact_id}, headers=auth_headers)
    assert resp.status_code == 201
    call_data = resp.json()
    call_id = call_data["id"]

    # 4. Live WebSocket conversation
    _install_fake_llm(monkeypatch)

    utterances = [
        "I need a 1000 lph RO system for my hotel",
        "500 lph is fine",
        "Pune",
        "Around 5 lakhs",
        "Within a month",
        "My name is Rahul Kumar",
    ]

    with TestClient(app) as test_client:
        token = auth_headers["Authorization"].split("Bearer ")[1]
        with test_client.websocket_connect(f"/ws/call/{call_id}?token={token}") as ws:
            opening = ws.receive_json()
            assert opening["type"] == "agent_reply"
            ws.receive_json()  # state_update

            for text in utterances:
                ws.send_json({"type": "customer_speech", "text": text, "confidence": 0.98})
                reply = ws.receive_json()
                assert reply["type"] == "agent_reply"
                ws.receive_json()  # state_update

            status_msg = ws.receive_json()
            assert status_msg["type"] == "call_status"
            assert status_msg["status"] == "completed"

    # 5. Verify Call in GET /calls/{id}
    resp = await client.get(f"/calls/{call_id}", headers=auth_headers)
    assert resp.status_code == 200
    call_detail = resp.json()
    assert call_detail["status"] == "completed"
    assert len(call_detail["turns"]) == 13
    assert call_detail["extracted_data"]["customer_name"] == "Rahul Kumar"
    assert call_detail["extracted_data"]["location"] == "Pune"
    assert call_detail["extracted_data"]["ro_capacity_lph"] is not None
    assert call_detail["summary"] is not None
    assert call_detail["summary"]["summary"]

    # 6. Verify Dashboard Stats updated
    resp = await client.get("/dashboard/stats", headers=auth_headers)
    assert resp.status_code == 200
    stats_after = resp.json()
    assert stats_after["total_calls"] == stats_before["total_calls"] + 1
    assert stats_after["completed_calls"] == stats_before["completed_calls"] + 1
