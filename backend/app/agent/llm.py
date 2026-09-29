"""LLM client — Gemini with bounded retries and a hard fallback contract.

Every public method either returns usable output or raises :class:`LLMError`;
callers are expected to catch it and fall back to deterministic behaviour.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

settings = get_settings()

_PLACEHOLDER_KEYS = {"", "your-gemini-api-key-here", "changeme"}
_FENCE_RE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)


class LLMError(Exception):
    """Raised when the LLM cannot produce a usable answer (after retries)."""


class LLMClient:
    """Thin async wrapper around the Google Gemini generate-content API."""

    def __init__(
        self,
        *,
        provider: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        max_retries: int | None = None,
    ) -> None:
        self.provider = provider if provider is not None else settings.LLM_PROVIDER
        self.model = model if model is not None else settings.LLM_MODEL
        self.api_key = api_key if api_key is not None else settings.GEMINI_API_KEY
        self.max_retries = max_retries if max_retries is not None else settings.LLM_MAX_RETRIES
        self.attempts = 0  # total calls made — asserted by retry tests
        self._client: Any = None

    @property
    def available(self) -> bool:
        """True when a real key is configured (placeholders don't count)."""
        return self.provider == "gemini" and self.api_key.strip().lower() not in _PLACEHOLDER_KEYS

    def _sdk(self) -> Any:
        if self._client is None:
            from google import genai  # imported lazily — keeps tests key-free

            self._client = genai.Client(api_key=self.api_key)
        return self._client

    async def _generate(self, prompt: str, system: str | None) -> str:
        """Single API call. Raises LLMError on transport/SDK problems."""
        client = self._sdk()
        config: dict[str, Any] = {}
        if system:
            config["system_instruction"] = system
        try:
            response = await client.aio.models.generate_content(
                model=self.model,
                contents=prompt,
                config=config or None,
            )
        except Exception as exc:  # SDK raises many shapes — normalise them all
            raise LLMError(f"LLM transport failure: {exc}") from exc
        text = getattr(response, "text", None)
        if not text or not text.strip():
            raise LLMError("LLM returned an empty response")
        return text.strip()

    async def chat(self, prompt: str, *, system: str | None = None) -> str:
        """Return a non-empty completion; retry then raise :class:`LLMError`."""
        if not self.available:
            raise LLMError("LLM unavailable (no API key configured)")
        last_error: LLMError | None = None
        for attempt in range(self.max_retries + 1):
            self.attempts += 1
            try:
                return await self._generate(prompt, system)
            except LLMError as exc:
                last_error = exc
                logger.warning(
                    "LLM attempt failed",
                    extra={"attempt": attempt + 1, "error": str(exc)},
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(min(0.05 * (2**attempt), 1.0))
        raise last_error or LLMError("LLM failed")

    async def chat_json(self, prompt: str, *, system: str | None = None) -> dict[str, Any]:
        """Return a parsed JSON object; malformed output consumes a retry too."""
        if not self.available:
            raise LLMError("LLM unavailable (no API key configured)")
        last_error: LLMError | None = None
        for attempt in range(self.max_retries + 1):
            self.attempts += 1
            try:
                raw = await self._generate(prompt, system)
            except LLMError as exc:
                last_error = exc
                logger.warning(
                    "LLM JSON attempt failed",
                    extra={"attempt": attempt + 1, "error": str(exc)},
                )
                continue
            try:
                payload = _FENCE_RE.sub(r"\1", raw.strip())
                parsed = json.loads(payload)
            except (json.JSONDecodeError, TypeError) as exc:
                last_error = LLMError(f"LLM returned invalid JSON: {exc}")
                logger.warning(
                    "LLM JSON parse failed",
                    extra={"attempt": attempt + 1, "error": str(exc)},
                )
                continue
            if not isinstance(parsed, dict):
                last_error = LLMError("LLM JSON was not an object")
                continue
            return parsed
        raise last_error or LLMError("LLM failed to produce JSON")


_default_client: LLMClient | None = None


def get_llm() -> LLMClient:
    """Process-wide default client (built once)."""
    global _default_client
    if _default_client is None:
        _default_client = LLMClient()
    return _default_client
