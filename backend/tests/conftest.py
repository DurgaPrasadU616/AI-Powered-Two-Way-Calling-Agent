"""Shared fixtures — test database, per-test engine, authenticated HTTP client.

IMPORTANT: ``DATABASE_URL`` is forced to the test database *before* any app
module is imported (settings are lru-cached on first read), so nothing in the
suite can ever touch the dev database.
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import AsyncGenerator, Awaitable, Callable
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _dev_database_url() -> str:
    env_file = BACKEND_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("DATABASE_URL="):
                return line.split("=", 1)[1].strip()
    return "postgresql+asyncpg://calling_agent:secret@localhost:5432/calling_agent_db"


TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    _dev_database_url().rsplit("/", 1)[0] + "/calling_agent_test",
)
# Force BEFORE importing anything from app.*
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

from app.api.deps import login_limiter  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402

settings = get_settings()
assert settings.DATABASE_URL == TEST_DATABASE_URL, "test process must not touch the dev DB"

_ADMIN_EMAIL = settings.ADMIN_EMAIL
# hashed once per pytest session — bcrypt rounds=12 is intentionally slow
_ADMIN_HASH = hash_password(settings.ADMIN_PASSWORD)

TRUNCATE_SQL = (
    "TRUNCATE TABLE call_events, call_summaries, call_extracted_data, "
    "call_turns, calls, contacts, admins RESTART IDENTITY CASCADE"
)


@pytest.fixture(scope="session", autouse=True)
def migrated_test_db() -> str:
    """Run ``alembic upgrade head`` against the test database once per session."""
    env = {**os.environ, "DATABASE_URL": TEST_DATABASE_URL}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, f"alembic failed:\n{result.stdout}\n{result.stderr}"
    return TEST_DATABASE_URL


@pytest.fixture(autouse=True)
def fresh_rate_limiter() -> None:
    """Every test starts with an empty login rate-limit window."""
    login_limiter.reset()
    yield
    login_limiter.reset()


@pytest_asyncio.fixture
async def db() -> AsyncGenerator:
    """Fresh engine + session factory per test; schema cleaned and admin seeded."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    engine = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.exec_driver_sql(TRUNCATE_SQL)
        await conn.execute(
            text("INSERT INTO admins (email, password_hash) VALUES (:e, :h)"),
            {"e": _ADMIN_EMAIL, "h": _ADMIN_HASH},
        )
    try:
        yield factory
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def client(db) -> AsyncGenerator[AsyncClient, None]:
    """HTTP client wired to the app with ``get_db`` overridden to the test DB."""

    async def override_get_db() -> AsyncGenerator:
        async with db() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient) -> dict[str, str]:
    """Valid bearer headers for the seeded admin."""
    response = await client.post(
        "/auth/login",
        json={"email": _ADMIN_EMAIL, "password": settings.ADMIN_PASSWORD},
    )
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def make_contact(
    client: AsyncClient, auth_headers: dict[str, str]
) -> Callable[..., Awaitable[dict]]:
    """Factory: create a contact and return its JSON."""

    async def _make(
        name: str = "Test Lead",
        phone: str = "+919876543210",
        **extra,
    ) -> dict:
        response = await client.post(
            "/contacts",
            json={"name": name, "phone_e164": phone, **extra},
            headers=auth_headers,
        )
        assert response.status_code == 201, response.text
        return response.json()

    return _make
