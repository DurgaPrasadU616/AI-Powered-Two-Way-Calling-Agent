"""Twilio voice and status callback webhooks with signature verification."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from twilio.request_validator import RequestValidator
from twilio.twiml.voice_response import Gather, Hangup, Say, VoiceResponse

from app.agent.dialogue import DialogueAgent, Phase
from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models.call import Call
from app.db.models.call_event import CallEvent
from app.db.models.call_extracted_data import CallExtractedData
from app.db.models.call_turn import CallTurn
from app.db.models.contact import Contact
from app.db.models.enums import CallOutcome, CallStatus, Speaker
from app.db.session import get_db

logger = get_logger(__name__)
settings = get_settings()

router = APIRouter(prefix="/webhooks/twilio", tags=["webhooks"])


async def verify_twilio_signature(
    request: Request,
    x_twilio_signature: str | None = Header(default=None, alias="X-Twilio-Signature"),
) -> None:
    """Validate Twilio webhook signature; reject with HTTP 403 if invalid."""
    # If no auth token is configured or in test mode without token, skip validation
    auth_token = settings.TWILIO_AUTH_TOKEN
    if not auth_token:
        # In test/dev environment without Twilio auth token, allow
        return

    if not x_twilio_signature:
        logger.warning("Missing X-Twilio-Signature header")
        raise HTTPException(status_code=403, detail="Missing Twilio signature")

    validator = RequestValidator(auth_token)
    url = str(request.url)

    # Starlette form parsing
    try:
        form = await request.form()
        params = dict(form)
    except Exception:
        params = {}

    if not validator.validate(url, params, x_twilio_signature):
        logger.warning("Invalid Twilio signature", extra={"url": url})
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")


@router.post("/voice", response_class=Response, summary="Twilio voice interaction webhook")
async def twilio_voice_webhook(
    request: Request,
    call_id: str = Query(...),
    _: None = Depends(verify_twilio_signature),
    session: AsyncSession = Depends(get_db),
) -> Response:
    """Handle incoming speech from Twilio or initial greeting, returning TwiML."""
    form_data = await request.form()
    speech_result = form_data.get("SpeechResult")
    call_uuid = uuid.UUID(call_id)

    call = await session.get(Call, call_uuid)
    if not call:
        twiml = VoiceResponse()
        twiml.say("Call not found. Goodbye.")
        twiml.hangup()
        return Response(content=str(twiml), media_type="application/xml")

    # If call not marked in progress, mark it
    if call.status == CallStatus.queued or call.status == CallStatus.ringing:
        call.status = CallStatus.in_progress
        session.add(CallEvent(call_id=call.id, event_type="call_started"))
        await session.commit()

    twiml = VoiceResponse()
    action_url = f"/api/v1/webhooks/twilio/voice?call_id={call_id}"

    if not speech_result:
        # Initial turn: greeting
        contact = await session.get(Contact, call.contact_id) if call.contact_id else None
        greeting_target = f" {contact.name}" if contact and contact.name else ""
        product_target = f" about {contact.product}" if contact and contact.product else " about water treatment systems"
        greeting = f"Hello{greeting_target}, this is the assistant calling from SERP Hawk{product_target}. Is now a good time?"

        # Save turn
        session.add(CallTurn(call_id=call.id, turn_index=0, speaker=Speaker.agent, message=greeting))
        await session.commit()

        gather = Gather(input="speech", action=action_url, method="POST", speech_timeout="auto")
        gather.say(greeting, voice="Polly.Aditi", language="en-IN")
        twiml.append(gather)
        # Fallback if no speech detected
        twiml.say("Are you still there?", voice="Polly.Aditi")
        twiml.redirect(action_url)
        return Response(content=str(twiml), media_type="application/xml")

    # Customer spoke
    customer_text = str(speech_result).strip()

    # Reconstruct agent from current state
    agent = DialogueAgent.from_settings()

    # Load existing turns to sync state
    existing_turns = (
        await session.scalars(select(CallTurn).where(CallTurn.call_id == call.id).order_by(CallTurn.turn_index))
    ).all()
    turn_idx = len(existing_turns)

    # Process through dialogue agent
    turn_output = await agent.handle(customer_text)

    # Save customer turn & agent reply turn
    session.add(CallTurn(call_id=call.id, turn_index=turn_idx, speaker=Speaker.customer, message=customer_text))
    session.add(CallTurn(call_id=call.id, turn_index=turn_idx + 1, speaker=Speaker.agent, message=turn_output.reply))

    # Upsert extracted slots
    extracted = await session.get(CallExtractedData, call.id)
    if extracted is None:
        extracted = CallExtractedData(call_id=call.id, raw_json=turn_output.slots)
        session.add(extracted)
    else:
        extracted.raw_json = turn_output.slots

    # Update columns
    for slot_name, val in turn_output.slots.items():
        if val and hasattr(extracted, slot_name):
            setattr(extracted, slot_name, val)
    if turn_output.slots.get("capacity"):
        extracted.ro_capacity_lph = turn_output.slots["capacity"]
    if turn_output.slots.get("company"):
        extracted.company_name = turn_output.slots["company"]

    await session.commit()

    if agent.ended:
        twiml.say(turn_output.reply, voice="Polly.Aditi", language="en-IN")
        twiml.hangup()
        call.status = CallStatus.completed
        call.outcome = CallOutcome.not_interested if agent.not_interested else CallOutcome.interested
        session.add(CallEvent(call_id=call.id, event_type="call_ended"))
        await session.commit()
    else:
        gather = Gather(input="speech", action=action_url, method="POST", speech_timeout="auto")
        gather.say(turn_output.reply, voice="Polly.Aditi", language="en-IN")
        twiml.append(gather)
        twiml.redirect(action_url)

    return Response(content=str(twiml), media_type="application/xml")


@router.post("/status", summary="Twilio call status callback webhook")
async def twilio_status_webhook(
    request: Request,
    call_id: str = Query(...),
    _: None = Depends(verify_twilio_signature),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Receive call status updates from Twilio (initiated, ringing, answered, completed, busy, no-answer)."""
    form_data = await request.form()
    twilio_status = (form_data.get("CallStatus") or "").lower()
    call_sid = form_data.get("CallSid")
    duration = form_data.get("CallDuration")

    call_uuid = uuid.UUID(call_id)
    call = await session.get(Call, call_uuid)
    if not call:
        return {"status": "ignored_unknown_call"}

    if call_sid and not call.provider_call_sid:
        call.provider_call_sid = str(call_sid)

    if twilio_status in ("ringing", "in-progress", "answered"):
        if call.status != CallStatus.in_progress:
            call.status = CallStatus.in_progress
            session.add(CallEvent(call_id=call.id, event_type="call_started", detail={"twilio_status": twilio_status}))
    elif twilio_status in ("busy", "no-answer"):
        call.status = CallStatus.no_answer
        call.outcome = CallOutcome.no_response
        session.add(CallEvent(call_id=call.id, event_type="no_answer", detail={"twilio_status": twilio_status}))
    elif twilio_status == "failed":
        call.status = CallStatus.failed
        call.outcome = CallOutcome.failed
        session.add(CallEvent(call_id=call.id, event_type="provider_error", detail={"twilio_status": twilio_status}))
    elif twilio_status in ("completed", "canceled"):
        if call.status != CallStatus.completed:
            call.status = CallStatus.completed
            if duration and duration.isdigit():
                call.duration_seconds = int(duration)
            session.add(CallEvent(call_id=call.id, event_type="call_ended", detail={"twilio_status": twilio_status}))

    await session.commit()
    logger.info("Twilio status callback processed", extra={"call_id": call_id, "twilio_status": twilio_status})
    return {"status": "ok", "call_status": call.status.value}
