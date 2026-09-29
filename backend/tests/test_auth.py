"""Phase 2 auth tests — login, JWT, 401s and brute-force rate limiting."""

from __future__ import annotations

from app.core.config import get_settings
from app.core.security import decode_access_token
from httpx import AsyncClient

settings = get_settings()


async def test_login_with_correct_password_returns_jwt(client: AsyncClient) -> None:
    response = await client.post(
        "/auth/login",
        json={"email": settings.ADMIN_EMAIL, "password": settings.ADMIN_PASSWORD},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["token_type"] == "bearer"
    payload = decode_access_token(body["access_token"])
    assert payload["sub"] == settings.ADMIN_EMAIL


async def test_login_with_wrong_password_returns_401(client: AsyncClient) -> None:
    response = await client.post(
        "/auth/login",
        json={"email": settings.ADMIN_EMAIL, "password": "definitely-wrong"},
    )
    assert response.status_code == 401
    assert response.json()["status_code"] == 401


async def test_login_with_unknown_email_returns_401(client: AsyncClient) -> None:
    response = await client.post(
        "/auth/login",
        json={"email": "nobody@example.com", "password": settings.ADMIN_PASSWORD},
    )
    assert response.status_code == 401


async def test_protected_route_without_token_returns_401(client: AsyncClient) -> None:
    response = await client.get("/contacts")
    assert response.status_code == 401
    assert response.headers.get("www-authenticate", "").lower().startswith("bearer")


async def test_protected_route_with_garbage_token_returns_401(client: AsyncClient) -> None:
    response = await client.get("/contacts", headers={"Authorization": "Bearer not.a.token"})
    assert response.status_code == 401


async def test_me_returns_admin_email(client: AsyncClient, auth_headers: dict) -> None:
    response = await client.get("/auth/me", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == {"email": settings.ADMIN_EMAIL}


async def test_login_rate_limit_triggers_429(client: AsyncClient) -> None:
    """5 failures exhaust the window (limit=5/60s); the 6th attempt is 429."""
    payload = {"email": settings.ADMIN_EMAIL, "password": "wrong-password"}
    for _ in range(settings.LOGIN_RATE_LIMIT):
        response = await client.post("/auth/login", json=payload)
        assert response.status_code == 401
    blocked = await client.post("/auth/login", json=payload)
    assert blocked.status_code == 429, blocked.text
    assert "Retry-After" in blocked.headers
    body = blocked.json()
    assert body["status_code"] == 429


async def test_rate_limit_is_per_email_key(client: AsyncClient) -> None:
    """Saturating one email must not block a different one."""
    for _ in range(settings.LOGIN_RATE_LIMIT):
        await client.post("/auth/login", json={"email": "blocked@example.com", "password": "x"})
    blocked = await client.post(
        "/auth/login", json={"email": "blocked@example.com", "password": "x"}
    )
    assert blocked.status_code == 429
    allowed = await client.post(
        "/auth/login",
        json={"email": settings.ADMIN_EMAIL, "password": settings.ADMIN_PASSWORD},
    )
    assert allowed.status_code == 200
