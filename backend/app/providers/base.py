"""Provider interfaces — calling, speech-to-text and text-to-speech.

Concrete implementations live in sibling modules; the active set is chosen
by the ``CALL_PROVIDER`` / ``STT_PROVIDER`` / ``TTS_PROVIDER`` settings.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.core.config import get_settings

settings = get_settings()


class CallProvider(ABC):
    """Owns the telephony side of a call (browser WebSocket today, Twilio later)."""

    name: str = "base"

    @abstractmethod
    async def start(self, call_id: str, phone_number: str) -> dict[str, Any]:
        """Begin the call; returns provider metadata (e.g. sid)."""

    @abstractmethod
    async def end(self, call_id: str) -> dict[str, Any]:
        """Terminate the call."""


class STTProvider(ABC):
    """Speech → text. In browser mode transcription happens client-side and
    arrives over the WebSocket as ``customer_speech``; server-side engines
    (whisper) would implement :meth:`transcribe`."""

    name: str = "base"

    @abstractmethod
    def supports_live_stream(self) -> bool: ...

    async def transcribe(self, audio: bytes, *, mime: str = "audio/webm") -> str:
        raise NotImplementedError(f"{self.name} has no server-side transcription")


class TTSProvider(ABC):
    """Text → speech. Browser mode speaks on the client via speechSynthesis;
    server-side engines would implement :meth:`synthesize`."""

    name: str = "base"

    @abstractmethod
    def speaks_client_side(self) -> bool: ...

    async def synthesize(self, text: str) -> bytes:
        raise NotImplementedError(f"{self.name} has no server-side synthesis")


# ── Browser implementations (Phase 4 default) ────────────────────────────────
class BrowserCallProvider(CallProvider):
    """Calls run over the app's own WebSocket — no external telephony."""

    name = "browser"

    async def start(self, call_id: str, phone_number: str) -> dict[str, Any]:
        return {"provider": self.name, "transport": "websocket", "call_id": call_id}

    async def end(self, call_id: str) -> dict[str, Any]:
        return {"provider": self.name, "call_id": call_id, "ended": True}


class BrowserSTTProvider(STTProvider):
    """Web Speech API runs in the browser (Chrome); server just receives text."""

    name = "browser"

    def supports_live_stream(self) -> bool:
        return True


class BrowserTTSProvider(TTSProvider):
    """speechSynthesis runs in the browser; server just sends text."""

    name = "browser"

    def speaks_client_side(self) -> bool:
        return True


_REGISTRY: dict[str, dict[str, type]] = {
    "call": {"browser": BrowserCallProvider},
    "stt": {"browser": BrowserSTTProvider},
    "tts": {"browser": BrowserTTSProvider},
}


def get_call_provider() -> CallProvider:
    return _REGISTRY["call"][settings.CALL_PROVIDER]()


def get_stt_provider() -> STTProvider:
    return _REGISTRY["stt"][settings.STT_PROVIDER]()


def get_tts_provider() -> TTSProvider:
    return _REGISTRY["tts"][settings.TTS_PROVIDER]()
