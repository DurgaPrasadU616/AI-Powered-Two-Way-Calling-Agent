"""bcrypt hashing + JWT round-trip (guards the passlib/bcrypt 5.x breakage)."""

from __future__ import annotations

from datetime import timedelta

import jwt as pyjwt
from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

settings = get_settings()


def test_hash_and_verify_roundtrip() -> None:
    hashed = hash_password("Admin@123")
    assert hashed.startswith("$2b$")
    assert verify_password("Admin@123", hashed) is True


def test_wrong_password_is_rejected() -> None:
    hashed = hash_password("Admin@123")
    assert verify_password("wrong-password", hashed) is False


def test_malformed_hash_never_raises() -> None:
    assert verify_password("anything", "not-a-real-hash") is False
    assert verify_password("anything", "") is False


def test_jwt_roundtrip() -> None:
    token = create_access_token("admin@example.com")
    payload = decode_access_token(token)
    assert payload["sub"] == "admin@example.com"


def test_jwt_expiry_is_honoured() -> None:
    token = create_access_token("admin@example.com", expires_delta=timedelta(minutes=-1))
    try:
        decode_access_token(token)
    except pyjwt.ExpiredSignatureError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expired token should not decode")
