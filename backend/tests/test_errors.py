"""Error hygiene — structured bodies only, never a stack trace (checks C14/E)."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from httpx import AsyncClient

BOOM_PATH = "/__audit_boom"
BOOM_SECRET = "intentional-marker-that-must-not-leak"


def test_unhandled_500_returns_structured_json_without_stack_trace() -> None:
    """A deliberate RuntimeError must yield {detail,status_code:500} and no traceback."""
    from app.main import app

    @app.get(BOOM_PATH)
    async def _boom() -> None:
        raise RuntimeError(BOOM_SECRET)

    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get(BOOM_PATH)
    finally:
        app.router.routes = [
            route for route in app.router.routes if getattr(route, "path", "") != BOOM_PATH
        ]

    assert response.status_code == 500
    body = response.json()
    assert body["detail"] == "Internal server error"
    assert body["status_code"] == 500
    assert "Traceback" not in response.text
    assert "RuntimeError" not in response.text
    assert BOOM_SECRET not in response.text
    assert 'File "' not in response.text


async def test_404_body_is_structured(client: AsyncClient, auth_headers: dict) -> None:
    response = await client.get(f"/calls/{uuid.uuid4()}", headers=auth_headers)
    assert response.status_code == 404
    body = response.json()
    assert body == {
        "detail": "Call not found",
        "status_code": 404,
    }


async def test_422_body_is_structured(client: AsyncClient, auth_headers: dict) -> None:
    response = await client.post(
        "/contacts",
        json={"name": "x", "phone_e164": "12345"},
        headers=auth_headers,
    )
    assert response.status_code == 422
    body = response.json()
    assert body["status_code"] == 422
    assert isinstance(body["detail"], list)
    assert "Traceback" not in response.text
    assert 'File "' not in response.text


async def test_unknown_route_is_structured_404(client: AsyncClient) -> None:
    response = await client.get("/no-such-endpoint")
    assert response.status_code == 404
    assert response.json()["status_code"] == 404
