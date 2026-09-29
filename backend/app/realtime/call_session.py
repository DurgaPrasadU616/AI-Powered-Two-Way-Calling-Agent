"""Live call session — the realtime voice loop behind ``/ws/call/{id}``.

Owns one websocket call: templated opening line, the agent dialogue loop,
silence prompts, barge-in logging, live persistence of every turn/extracted
slot, and end/disconnect handling with summary generation (Agent.md §9).
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agent.dialogue import DialogueAgent
from app.agent.llm import get_llm
from app.agent.slots import DB_COLUMNS
from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models.call import Call
from app.db.models.call_event import CallEvent
from app.db.models.call_extracted_data import CallExtractedData
from app.db.models.call_turn import CallTurn
from app.db.models.contact import Contact
from app.db.models.enums import CallStatus, Speaker
from app.services import call_service, summary_service

logger = get_logger(__name__)
settings = get_settings()

SendFn = Callable[[dict[str, Any]], Awaitable[None]]

_OPENING = (
    "Hello{name}, this is the assistant calling from SERP Hawk about "
    "{product}. Is now a good time?"
)
_NUDGE = "Are you still there?"
# reason → (call_status, call_events.event_type)
_END_STATES: dict[str, tuple[CallStatus, str]] = {
    "completed": (CallStatus.completed, "call_ended"),
    "silence_timeout": (CallStatus.completed, "silence_timeout"),
    "disconnected": (CallStatus.disconnected, "disconnected"),
}


class CallSession:
    """One live call: dialogue loop + persistence + realtime messages."""

    def __init__(
        self,
        call_id: uuid.UUID,
        session_factory: async_sessionmaker[AsyncSession],
        send: SendFn,
        *,
        llm: Any = None,
        silence_seconds: float | None = None,
        max_prompts: int | None = None,
    ) -> None:
        self.call_id = call_id
        self.session_factory = session_factory
        self.send = send
        self.agent = DialogueAgent(llm=get_llm() if llm is None else llm)
        self.silence_seconds = (
            settings.SILENCE_PROMPT_SECONDS if silence_seconds is None else silence_seconds
        )
        self.max_prompts = settings.SILENCE_MAX_PROMPTS if max_prompts is None else max_prompts
        self.closed = False
        self.finished = False
        self._turn_index = -1
        self._speech = asyncio.Event()
        self._silence_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()

    # ── outbound helpers ────────────────────────────────────────────────────
    async def _emit(self, message: dict[str, Any]) -> None:
        """Send *message* to the client; the socket may already be gone."""
        try:
            await self.send(message)
        except Exception:  # pragma: no cover - client already disconnected
            logger.debug("WS send failed", extra={"call_id": str(self.call_id)})

    async def _emit_state(self) -> None:
        await self._emit(
            {
                "type": "state_update",
                "slots": self.agent.slots.as_dict(),
                "phase": self.agent.phase.value,
                "pending_slot": self.agent.pending_slot,
            }
        )

    # ── lifecycle ───────────────────────────────────────────────────────────
    async def start(self) -> None:
        """Mark the call in progress, send the templated opening line."""
        async with self.session_factory() as db:
            call = await db.get(Call, self.call_id)
            if call is None:
                raise LookupError(f"call {self.call_id} not found")
            contact = await db.get(Contact, call.contact_id) if call.contact_id else None
            call.status = CallStatus.in_progress
            call.start_time = datetime.now(tz=UTC)
            db.add(CallEvent(call_id=self.call_id, event_type="call_started"))
            max_index = await db.scalar(
                select(func.max(CallTurn.turn_index)).where(CallTurn.call_id == self.call_id)
            )
            self._turn_index = int(max_index) if max_index is not None else -1
            opening = self._opening_for(contact)
            await self._save_turn(db, Speaker.agent, opening, None)
            await db.commit()

        await self._emit({"type": "agent_reply", "text": opening, "turn_index": self._turn_index})
        await self._emit_state()
        self._silence_task = asyncio.create_task(self._silence_loop())

    def _opening_for(self, contact: Contact | None) -> str:
        if contact is None:
            return _OPENING.format(name="", product="water treatment systems")
        name = f" {contact.name}" if contact.name else ""
        product = contact.product or "water treatment systems"
        return _OPENING.format(name=name, product=product)

    async def on_customer_speech(self, text: str, confidence: float | None = None) -> None:
        """Process one utterance: persist both turns, reply, maybe wrap up."""
        if self.closed:
            await self._emit({"type": "error", "detail": "call already ended"})
            return
        self._speech.set()
        turn = await self.agent.handle(text)
        async with self._lock:
            if self.closed:
                return
            async with self.session_factory() as db:
                if turn.extra.get("llm_error"):
                    db.add(
                        CallEvent(
                            call_id=self.call_id,
                            event_type="llm_failure",
                            detail={"error": turn.extra["llm_error"]},
                        )
                    )
                await self._save_turn(db, Speaker.customer, text, confidence)
                await self._save_turn(db, Speaker.agent, turn.reply, None)
                await self._upsert_extracted(db)
                await db.commit()

            await self._emit(
                {"type": "agent_reply", "text": turn.reply, "turn_index": self._turn_index}
            )
            await self._emit_state()
            should_finish = self.agent.ended

        if should_finish:
            await self.finish("completed")

    async def on_interrupt(self) -> None:
        """Barge-in: client cancels TTS; we log ``call_events.interrupted``."""
        if self.closed:
            return
        async with self.session_factory() as db:
            db.add(
                CallEvent(
                    call_id=self.call_id,
                    event_type="interrupted",
                    detail={"phase": self.agent.phase.value},
                )
            )
            await db.commit()
        logger.info("Barge-in", extra={"call_id": str(self.call_id)})

    async def on_end_call(self) -> None:
        """Client pressed End Call."""
        await self.finish("completed")

    async def on_disconnect(self) -> None:
        """Socket dropped: status=disconnected, partial transcript summarized."""
        if not self.finished:
            await self.finish("disconnected")

    async def finish(self, reason: str) -> None:
        """End the call once: status/end_time/duration/event + summary."""
        async with self._lock:
            if self.finished:
                return
            self.finished = True
            self.closed = True
            task = self._silence_task
            self._silence_task = None
            if task is not None and task is not asyncio.current_task():
                task.cancel()  # never cancel ourselves (finish may run inside it)

            status, event_type = _END_STATES[reason]
            async with self.session_factory() as db:
                call = await call_service.get_call(db, self.call_id)
                if call is not None:
                    now = datetime.now(tz=UTC)
                    call.end_time = now
                    anchor = call.start_time or call.created_at
                    if anchor is not None:
                        if anchor.tzinfo is None:
                            anchor = anchor.replace(tzinfo=UTC)
                        call.duration_seconds = max(0, int((now - anchor).total_seconds()))
                    call.status = status
                    db.add(CallEvent(call_id=self.call_id, event_type=event_type))
                    await summary_service.generate_and_store_summary(
                        db, self.call_id, not_interested=self.agent.not_interested
                    )
                    await db.commit()
                    duration = call.duration_seconds
                else:  # pragma: no cover - call vanished mid-flight
                    duration = None
                if not self.agent.ended:
                    # disconnected/timeout mid-conversation: persist what we have
                    await self._upsert_extracted(db)
                    await db.commit()

            await self._emit(
                {
                    "type": "call_status",
                    "status": status.value,
                    "reason": reason,
                    "duration_seconds": duration,
                }
            )
            logger.info(
                "Call session finished",
                extra={"call_id": str(self.call_id), "reason": reason, "status": status.value},
            )

    # ── silence handling ────────────────────────────────────────────────────
    async def _silence_loop(self) -> None:
        """Prompt after each silent interval, then end with silence_timeout."""
        prompts = 0
        while not self.closed:
            self._speech.clear()
            try:
                await asyncio.wait_for(self._speech.wait(), timeout=self.silence_seconds)
                continue  # customer spoke — restart the interval
            except TimeoutError:
                pass
            prompts += 1
            if prompts > self.max_prompts:
                await self.finish("silence_timeout")
                return
            await self._save_and_send_nudge()

    async def _save_and_send_nudge(self) -> None:
        async with self._lock:
            if self.closed:
                return
            async with self.session_factory() as db:
                await self._save_turn(db, Speaker.agent, _NUDGE, None)
                await db.commit()
            await self._emit(
                {"type": "agent_reply", "text": _NUDGE, "turn_index": self._turn_index}
            )

    # ── persistence ─────────────────────────────────────────────────────────
    async def _save_turn(
        self,
        db: AsyncSession,
        speaker: Speaker,
        message: str,
        confidence: float | None,
    ) -> None:
        self._turn_index += 1
        db.add(
            CallTurn(
                call_id=self.call_id,
                turn_index=self._turn_index,
                speaker=speaker,
                message=message,
                confidence=confidence,
            )
        )

    async def _upsert_extracted(self, db: AsyncSession) -> None:
        """Live mirror of agent slots into ``call_extracted_data``."""
        slots = self.agent.slots.as_dict()
        if not any(slots.values()):
            return
        row = await db.get(CallExtractedData, self.call_id)
        if row is None:
            row = CallExtractedData(call_id=self.call_id)
            db.add(row)
        for slot, column in DB_COLUMNS.items():
            value = slots.get(slot)
            if value:
                setattr(row, column, value)
        row.raw_json = {k: v for k, v in slots.items() if v}
        row.updated_at = datetime.now(tz=UTC)
        await db.flush()


__all__ = ["CallSession"]
