"""Settings must load from backend/.env with safe defaults."""

from __future__ import annotations

from app.core.config import Settings, get_settings


def test_settings_defaults_are_sane() -> None:
    settings = Settings(_env_file=None)
    assert settings.APP_ENV == "development"
    assert settings.JWT_ALGORITHM == "HS256"
    assert settings.JWT_EXPIRE_MINUTES > 0
    assert settings.CALL_PROVIDER in {"browser", "twilio"}
    assert settings.STT_PROVIDER in {"browser", "whisper"}
    assert settings.TTS_PROVIDER in {"browser", "edge"}
    assert settings.DATABASE_URL.startswith("postgresql+asyncpg://")


def test_cors_origin_is_a_single_origin() -> None:
    settings = Settings(_env_file=None)
    assert settings.FRONTEND_ORIGIN.startswith("http")
    assert "," not in settings.FRONTEND_ORIGIN


def test_get_settings_is_cached() -> None:
    assert get_settings() is get_settings()
