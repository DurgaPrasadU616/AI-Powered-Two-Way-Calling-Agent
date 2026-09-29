"""Security utilities — password hashing and JWT creation/verification.

Expanded with protected-route dependency in Phase 2.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from app.core.config import get_settings

settings = get_settings()

_BCRYPT_ROUNDS = 12


# ── Password helpers ───────────────────────────────────────────────────────────


def hash_password(plain: str) -> str:
    """Return bcrypt hash of *plain* password (standard $2b$ format)."""
    digest = bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=_BCRYPT_ROUNDS))
    return digest.decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if *plain* matches *hashed*. Never raises on malformed hashes."""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# ── JWT helpers ────────────────────────────────────────────────────────────────


def create_access_token(
    subject: Any,
    expires_delta: timedelta | None = None,
) -> str:
    """Encode a signed JWT with an expiry claim."""
    expire = datetime.now(tz=UTC) + (
        expires_delta or timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    )
    payload = {"sub": str(subject), "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and verify a JWT. Raises jwt.PyJWTError on failure."""
    return jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )
