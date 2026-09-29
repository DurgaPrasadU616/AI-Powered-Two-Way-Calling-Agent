"""WebSocket router — ``WS /ws/call/{call_id}`` (Agent.md §9)."""

from __future__ import annotations

import json
import uuid
from contextlib import suppress

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models.call import Call
from app.db.models.enums import CallStatus
from app.realtime.call_session import CallSession

logger = get_logger(__name__)
settings = get_settings()

router = APIRouter()

_ENDED_STATUSES = (
    CallStatus.completed,
    CallStatus.failed,
    CallStatus.no_answer,
    CallStatus.disconnected,
    CallStatus.invalid_number,
)


async def _error(websocket: WebSocket, detail: str) -> None:
    await websocket.send_json({"type": "error", "detail": detail})


@router.websocket("/ws/call/{call_id}")
async def ws_call(websocket: WebSocket, call_id: str) -> None:
    """One live call: handshake → opening line → dialogue loop → finish.

    Message contract: client→server ``customer_speech`` / ``interrupt`` /
    ``end_call``; server→client ``agent_reply`` / ``state_update`` /
    ``call_status`` / ``error``.
    """
    await websocket.accept()
    try:
        call_uuid = uuid.UUID(call_id)
    except ValueError:
        await _error(websocket, "invalid call id")
        await websocket.close(code=1008)
        return

    # NullPool: every connection is opened/closed inside this socket's event
    # loop — safe under pytest's portal loop as well as uvicorn's.
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )
    session: CallSession | None = None
    try:
        async with factory() as db:
            call = await db.get(Call, call_uuid)
        if call is None:
            await _error(websocket, "call not found")
            await websocket.close(code=1008)
            return
        if call.status in _ENDED_STATUSES:
            await _error(websocket, "call already ended")
            await websocket.close(code=1008)
            return

        session = CallSession(call_uuid, factory, websocket.send_json)
        await session.start()

        while True:
            raw = await websocket.receive_text()
            try:
                message = json.loads(raw)
                if not isinstance(message, dict):
                    raise ValueError("not an object")
            except ValueError:
                await _error(websocket, "invalid message: expected a JSON object")
                continue

            kind = message.get("type")
            if kind == "customer_speech":
                text = str(message.get("text") or "").strip()
                if not text:
                    await _error(websocket, "customer_speech requires non-empty text")
                    continue
                confidence = message.get("confidence")
                if not isinstance(confidence, (int, float)):
                    confidence = None
                await session.on_customer_speech(text, float(confidence))
            elif kind == "interrupt":
                await session.on_interrupt()
            elif kind == "end_call":
                await session.on_end_call()
                break
            else:
                await _error(websocket, f"unknown message type: {kind!r}")

        with suppress(Exception):
            await websocket.close()
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("WS call crashed", extra={"call_id": call_id})
        with suppress(Exception):
            await _error(websocket, "internal error")
    finally:
        if session is not None:
            await session.on_disconnect()
        await engine.dispose()


__all__ = ["router"]
