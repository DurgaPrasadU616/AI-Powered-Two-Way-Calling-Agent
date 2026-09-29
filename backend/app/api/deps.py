"""Shared API dependencies — current user (JWT) and login rate limiting."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import decode_access_token
from app.db.models.admin import Admin
from app.db.session import get_db

settings = get_settings()


# ── Authentication ─────────────────────────────────────────────────────────────
async def get_current_user(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> Admin:
    """Resolve the Admin behind ``Authorization: Bearer <jwt>``; 401 otherwise."""
    auth_header = request.headers.get("Authorization", "")
    scheme, _, token = auth_header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=401, detail="Not authenticated", headers={"WWW-Authenticate": "Bearer"}
        )
    try:
        payload = decode_access_token(token)
    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    admin = await session.scalar(select(Admin).where(Admin.email == payload.get("sub", "")))
    if admin is None:
        raise HTTPException(
            status_code=401, detail="Not authenticated", headers={"WWW-Authenticate": "Bearer"}
        )
    return admin


# ── Rate limiting (in-memory sliding window) ──────────────────────────────────
class SlidingWindowLimiter:
    """Thread-safe sliding-window counter keyed by an arbitrary string."""

    def __init__(self, max_hits: int, window_seconds: int) -> None:
        self.max_hits = max_hits
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        """Record a hit for *key*; return False when the window is saturated."""
        now = time.monotonic()
        with self._lock:
            bucket = self._hits[key]
            while bucket and bucket[0] <= now - self.window_seconds:
                bucket.popleft()
            if len(bucket) >= self.max_hits:
                return False
            bucket.append(now)
            return True

    def reset(self, key: str | None = None) -> None:
        """Forget one key (or everything — used by tests)."""
        with self._lock:
            if key is None:
                self._hits.clear()
            else:
                self._hits.pop(key, None)


login_limiter = SlidingWindowLimiter(
    max_hits=settings.LOGIN_RATE_LIMIT,
    window_seconds=settings.LOGIN_RATE_WINDOW_SECONDS,
)


async def login_rate_limit(request: Request) -> None:
    """Per-IP+email limiter for POST /auth/login → 429 when saturated.

    The body is read here and cached on the request, so the endpoint's own
    body parsing still works (Starlette returns the cached bytes).
    """
    client_ip = request.client.host if request.client else "unknown"
    email = "unknown"
    try:
        payload = await request.json()
        if isinstance(payload, dict) and isinstance(payload.get("email"), str):
            email = payload["email"].strip().lower()[:255]
    except Exception:
        pass
    key = f"{client_ip}:{email}"
    if not login_limiter.allow(key):
        raise HTTPException(
            status_code=429,
            detail="Too many login attempts, please try again later",
            headers={"Retry-After": str(settings.LOGIN_RATE_WINDOW_SECONDS)},
        )
