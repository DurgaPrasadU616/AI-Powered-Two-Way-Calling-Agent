"""Phase 2 dashboard stats — numbers verified against hand-inserted rows."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from httpx import AsyncClient

from tests.test_calls import _insert_call


async def test_stats_on_empty_database(client: AsyncClient, auth_headers: dict) -> None:
    response = await client.get("/dashboard/stats", headers=auth_headers)
    assert response.status_code == 200, response.text
    assert response.json() == {
        "total_calls": 0,
        "completed_calls": 0,
        "failed_calls": 0,
        "interested_leads": 0,
        "followups_required": 0,
        "avg_duration_seconds": 0.0,
    }


async def test_stats_match_inserted_rows(client: AsyncClient, auth_headers: dict, db) -> None:
    """5 rows with known properties → 6 known numbers."""
    now = datetime.now(tz=UTC)
    from app.db.models.enums import CallOutcome, CallStatus, LeadStatus

    # A: completed, 100s, interested
    await _insert_call(
        db,
        status=CallStatus.completed,
        duration_seconds=100,
        outcome=CallOutcome.interested,
        lead_status=LeadStatus.hot,
        start_time=now - timedelta(seconds=100),
        end_time=now,
    )
    # B: completed, 300s, follow-up required
    await _insert_call(
        db,
        status=CallStatus.completed,
        duration_seconds=300,
        followup_required=True,
        start_time=now - timedelta(seconds=300),
        end_time=now,
    )
    # C: failed
    await _insert_call(db, status=CallStatus.failed)
    # D: still queued, follow-up required
    await _insert_call(db, status=CallStatus.queued, followup_required=True)
    # E: no answer → counts as failed
    await _insert_call(db, status=CallStatus.no_answer)

    response = await client.get("/dashboard/stats", headers=auth_headers)
    assert response.status_code == 200, response.text
    stats = response.json()
    assert stats["total_calls"] == 5
    assert stats["completed_calls"] == 2
    assert stats["failed_calls"] == 2  # failed + no_answer
    assert stats["interested_leads"] == 1  # outcome == interested
    assert stats["followups_required"] == 2  # B + D
    assert stats["avg_duration_seconds"] == 200.0  # (100 + 300) / 2


async def test_stats_require_auth(client: AsyncClient) -> None:
    response = await client.get("/dashboard/stats")
    assert response.status_code == 401
