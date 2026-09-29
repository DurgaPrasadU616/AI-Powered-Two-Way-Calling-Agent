"""Phase 1 smoke tests: app boots, /health answers, global handlers never leak traces."""

from __future__ import annotations

from app.main import app
from httpx import ASGITransport, AsyncClient


async def test_health_returns_ok() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "ai-calling-agent"
    assert body["version"] == "0.1.0"


async def test_docs_is_available() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/health" in paths


async def test_unknown_route_returns_structured_404() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/definitely-not-a-route")

    assert response.status_code == 404
    body = response.json()
    assert "detail" in body
    assert body["status_code"] == 404
