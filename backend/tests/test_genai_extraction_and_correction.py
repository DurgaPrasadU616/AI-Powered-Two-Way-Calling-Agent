"""Tests for GenAI slot extraction, correction handling, question-answering, and prompt centralization."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agent.dialogue import DialogueAgent
from app.agent.extractor import ExtractedSlots, extract_slots_llm
from app.agent.prompts import DIALOGUE_SYSTEM_PROMPT, EXTRACTION_SYSTEM_PROMPT, SUMMARY_SYSTEM_PROMPT
from app.core.config import get_settings

settings = get_settings()


@pytest.mark.asyncio
async def test_llm_slot_extraction_success():
    """extract_slots_llm returns validated ExtractedSlots from LLM JSON response."""
    mock_llm = MagicMock()
    mock_llm.available = True
    mock_llm.chat_json = AsyncMock(
        return_value={
            "requirement": "Industrial RO Plant",
            "capacity": "2000 LPH",
            "location": "Chennai",
            "budget": "5 lakhs",
            "timeline": "2 months",
            "customer_name": "Suresh Raina",
            "company": "Raina Foods",
            "application": "factory",
            "additional_requirements": "TDS 3000 ppm",
            "is_correction": False,
            "corrected_slot": None,
        }
    )

    res = await extract_slots_llm(mock_llm, "We need 2000 LPH for our factory in Chennai", {})
    assert res is not None
    assert isinstance(res, ExtractedSlots)
    assert res.capacity == "2000 LPH"
    assert res.location == "Chennai"
    assert res.application == "factory"


@pytest.mark.asyncio
async def test_llm_slot_extraction_fallback_on_error():
    """When LLM extraction fails or raises, it gracefully returns None without crashing."""
    mock_llm = MagicMock()
    mock_llm.available = True
    mock_llm.chat_json = AsyncMock(side_effect=RuntimeError("Quota limit reached"))

    res = await extract_slots_llm(mock_llm, "500 LPH", {})
    assert res is None


@pytest.mark.asyncio
async def test_slot_correction_updates_previously_filled_value():
    """Customer correcting a previous value ('actually make it 1000 LPH') overwrites the slot."""
    agent = DialogueAgent()
    # 1. Provide initial requirement
    turn1 = await agent.handle("I need an RO system for my hotel")
    assert agent.slots.values["requirement"] == "an RO system for my hotel"

    # 2. Answer capacity with 500 LPH
    turn2 = await agent.handle("500 LPH")
    assert agent.slots.values["capacity"] == "500 LPH"

    # 3. Correct capacity to 1000 LPH
    turn3 = await agent.handle("Actually make it 1000 LPH")
    assert agent.slots.values["capacity"] == "1000 LPH"


@pytest.mark.asyncio
async def test_customer_question_answers_and_returns_to_missing_slot():
    """When customer asks a question ('what is the price?'), agent answers and asks the missing slot."""
    agent = DialogueAgent()
    await agent.handle("I need an RO system for my hotel")
    assert agent.pending_slot == "capacity"

    turn = await agent.handle("What is the price?")
    # Contains price explanation
    assert "pricing" in turn.reply.lower() or "quote" in turn.reply.lower() or "fair question" in turn.reply.lower()
    # Still directs customer to capacity
    assert "capacity" in turn.reply.lower() or "what capacity" in turn.reply.lower()
    assert agent.pending_slot == "capacity"


def test_prompts_centralized_and_model_from_env():
    """Prompts live in app.agent.prompts and model identifier comes from settings."""
    assert len(DIALOGUE_SYSTEM_PROMPT) > 20
    assert len(EXTRACTION_SYSTEM_PROMPT) > 20
    assert len(SUMMARY_SYSTEM_PROMPT) > 20
    assert settings.LLM_MODEL == "gemini-2.5-flash"
