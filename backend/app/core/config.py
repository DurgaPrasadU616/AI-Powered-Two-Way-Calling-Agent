"""Application configuration — reads all env vars via pydantic-settings."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/.env — resolved from this file so the app works from any CWD.
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── App ────────────────────────────────────────────────────────────
    APP_ENV: str = "development"
    SECRET_KEY: str = "change-me-in-production-min-32-chars"
    SQL_ECHO: bool = False

    # ── Database ───────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://calling_agent:secret@localhost:5432/calling_agent_db"

    # ── Admin (env-configured, no self-registration) ───────────────────
    ADMIN_EMAIL: str = "admin@sephawk.com"
    ADMIN_PASSWORD: str = "Admin@123"

    # ── JWT ────────────────────────────────────────────────────────────
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440

    # ── Rate limiting (login brute-force guard) ────────────────────────
    LOGIN_RATE_LIMIT: int = 5
    LOGIN_RATE_WINDOW_SECONDS: int = 60

    # ── LLM ────────────────────────────────────────────────────────────
    GEMINI_API_KEY: str = ""
    LLM_PROVIDER: str = "gemini"
    LLM_MODEL: str = "gemini-2.5-flash"
    LLM_MAX_RETRIES: int = 2

    # ── STT / TTS / Calling ────────────────────────────────────────────
    STT_PROVIDER: str = "browser"
    TTS_PROVIDER: str = "browser"
    CALL_PROVIDER: str = "browser"

    # ── Realtime call session (Phase 4) ───────────────────────────────
    SILENCE_PROMPT_SECONDS: float = 7.0
    SILENCE_MAX_PROMPTS: int = 2

    # ── CORS ───────────────────────────────────────────────────────────
    FRONTEND_ORIGIN: str = "http://localhost:3000"

    # ── Twilio (optional, Phase 7) ─────────────────────────────────────
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_PHONE_NUMBER: str = ""


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings instance (reads .env once)."""
    return Settings()
