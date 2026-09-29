"""Twilio CallProvider implementation — places and ends calls via Twilio REST API.

Enabled when CALL_PROVIDER=twilio in application settings.
"""

from __future__ import annotations

import asyncio
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger
from app.providers.base import CallProvider

logger = get_logger(__name__)
settings = get_settings()


class TwilioCallProvider(CallProvider):
    """Telephony provider backed by the official Twilio Python SDK."""

    name = "twilio"

    def __init__(
        self,
        account_sid: str | None = None,
        auth_token: str | None = None,
        from_number: str | None = None,
        public_base_url: str | None = None,
    ) -> None:
        self.account_sid = account_sid or settings.TWILIO_ACCOUNT_SID
        self.auth_token = auth_token or settings.TWILIO_AUTH_TOKEN
        self.from_number = from_number or settings.TWILIO_FROM_NUMBER or settings.TWILIO_PHONE_NUMBER
        self.public_base_url = (public_base_url or settings.PUBLIC_BASE_URL).rstrip("/")
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            from twilio.rest import Client

            if not self.account_sid or not self.auth_token:
                raise RuntimeError("Twilio credentials not configured (TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN)")
            self._client = Client(self.account_sid, self.auth_token)
        return self._client

    async def start(self, call_id: str, phone_number: str) -> dict[str, Any]:
        """Place an outbound call via Twilio REST API."""
        return await self.start_call(call_id, phone_number)

    async def start_call(self, call_id: str, phone_number: str) -> dict[str, Any]:
        """Place an outbound call with TwiML voice URL and status callback."""
        voice_url = f"{self.public_base_url}/api/v1/webhooks/twilio/voice?call_id={call_id}"
        status_url = f"{self.public_base_url}/api/v1/webhooks/twilio/status?call_id={call_id}"

        def _place():
            client = self._get_client()
            return client.calls.create(
                to=phone_number,
                from_=self.from_number,
                url=voice_url,
                status_callback=status_url,
                status_callback_event=["initiated", "ringing", "answered", "completed"],
                status_callback_method="POST",
            )

        try:
            call = await asyncio.to_thread(_place)
            logger.info("Twilio call initiated", extra={"call_id": call_id, "sid": call.sid})
            return {
                "provider": self.name,
                "call_sid": getattr(call, "sid", "mock_sid"),
                "call_id": call_id,
                "status": getattr(call, "status", "queued"),
            }
        except Exception as exc:
            logger.error("Failed to start Twilio call", extra={"call_id": call_id, "error": str(exc)})
            raise

    async def end(self, call_id: str) -> dict[str, Any]:
        """Terminate call via hangup."""
        return await self.hangup(call_id)

    async def hangup(self, call_id: str, call_sid: str | None = None) -> dict[str, Any]:
        """Hangup an in-progress Twilio call."""
        if not call_sid:
            logger.info("Twilio hangup called without sid; treating as ended", extra={"call_id": call_id})
            return {"provider": self.name, "call_id": call_id, "ended": True}

        def _hangup():
            client = self._get_client()
            return client.calls(call_sid).update(status="completed")

        try:
            await asyncio.to_thread(_hangup)
            return {"provider": self.name, "call_id": call_id, "ended": True, "call_sid": call_sid}
        except Exception as exc:
            logger.warning("Twilio hangup error", extra={"call_id": call_id, "error": str(exc)})
            return {"provider": self.name, "call_id": call_id, "ended": False, "error": str(exc)}
