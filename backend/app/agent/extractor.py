"""LLM-powered slot extraction with strict Pydantic validation."""

from __future__ import annotations

import asyncio

from pydantic import BaseModel, Field

from app.agent.llm import LLMClient, LLMError
from app.agent.prompts import EXTRACTION_SYSTEM_PROMPT
from app.core.logging import get_logger

logger = get_logger(__name__)


class ExtractedSlots(BaseModel):
    """Pydantic schema for real-time customer slot extraction."""

    requirement: str | None = None
    capacity: str | None = None
    location: str | None = None
    budget: str | None = None
    timeline: str | None = None
    customer_name: str | None = None
    company: str | None = None
    application: str | None = None
    additional_requirements: str | None = None
    is_correction: bool = Field(default=False)
    corrected_slot: str | None = None


async def extract_slots_llm(
    llm: LLMClient | None,
    text: str,
    current_slots: dict[str, str | None],
) -> ExtractedSlots | None:
    """Extract slots from a customer utterance using LLM with Pydantic validation.

    Degrades gracefully to None on timeout or LLM error, allowing deterministic fallback.
    """
    if llm is None or not llm.available:
        return None

    filled_ctx = ", ".join(f"{k}={v}" for k, v in current_slots.items() if v) or "none"
    prompt = (
        f"Customer said: {text!r}\n"
        f"Previously collected values: {filled_ctx}\n"
        "Extract any mentioned qualification details into the requested JSON schema."
    )

    try:
        # Strict timeout of 2.0s so voice latency is not blocked
        data = await asyncio.wait_for(
            llm.chat_json(prompt, system=EXTRACTION_SYSTEM_PROMPT),
            timeout=2.0,
        )
        validated = ExtractedSlots.model_validate(data)
        logger.debug(
            "LLM slot extraction successful",
            extra={"extracted": validated.model_dump(exclude_none=True)},
        )
        return validated
    except (TimeoutError, LLMError, Exception) as exc:
        logger.debug(
            "LLM slot extraction skipped or failed, using rule fallback", extra={"error": str(exc)}
        )
        return None
