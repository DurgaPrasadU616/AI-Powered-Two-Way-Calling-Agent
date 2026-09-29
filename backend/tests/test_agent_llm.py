"""LLM client + fallback tests — audit checks D19 (retry, then fallback)."""

from __future__ import annotations

import json

import pytest
from app.agent.dialogue import DialogueAgent
from app.agent.llm import LLMClient, LLMError
from app.agent.summary import CallSummaryCreate, generate_summary


def _client(monkeypatch, side_effects, *, max_retries: int = 2) -> LLMClient:
    """Client whose underlying transport replays *side_effects* (str | Exception)."""
    client = LLMClient(api_key="fake-test-key", max_retries=max_retries)
    remaining = list(side_effects)

    async def _generate(prompt, system=None):  # noqa: ARG001
        item = remaining.pop(0) if remaining else side_effects[-1]
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(client, "_generate", _generate)
    return client


# ── retries ───────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_chat_retries_then_succeeds(monkeypatch) -> None:
    client = _client(monkeypatch, [LLMError("blip"), LLMError("blip"), "Hello there"])
    result = await client.chat("hi")
    assert result == "Hello there"
    assert client.attempts == 3  # 2 failures + 1 success


@pytest.mark.asyncio
async def test_chat_raises_after_exhausting_retries(monkeypatch) -> None:
    client = _client(monkeypatch, [LLMError("boom")])
    with pytest.raises(LLMError):
        await client.chat("hi")
    assert client.attempts == 3  # max_retries=2 → 3 attempts total


@pytest.mark.asyncio
async def test_chat_json_rejects_bad_json_then_raises(monkeypatch) -> None:
    client = _client(monkeypatch, ["this is not json", "{'also': 'nope'}", "still not"])
    with pytest.raises(LLMError, match="invalid JSON|not an object"):
        await client.chat_json("give me json")
    assert client.attempts == 3  # every bad payload consumed exactly one attempt


@pytest.mark.asyncio
async def test_chat_json_accepts_json_after_bad_attempt(monkeypatch) -> None:
    client = _client(monkeypatch, ["nonsense", json.dumps({"ok": True})])
    assert await client.chat_json("json please") == {"ok": True}
    assert client.attempts == 2


@pytest.mark.asyncio
async def test_chat_json_strips_code_fences(monkeypatch) -> None:
    payload = json.dumps({"a": 1})
    client = _client(monkeypatch, [f"```json\n{payload}\n```"])
    assert await client.chat_json("x") == {"a": 1}


@pytest.mark.asyncio
async def test_unavailable_client_fails_fast_without_attempts() -> None:
    client = LLMClient(api_key="your-gemini-api-key-here")  # placeholder → unavailable
    assert client.available is False
    with pytest.raises(LLMError):
        await client.chat("hi")
    assert client.attempts == 0  # never touched the network


# ── agent falls back when the LLM dies (D19 reply fallback) ──────────────────
@pytest.mark.asyncio
async def test_agent_uses_fallback_reply_when_llm_fails(monkeypatch) -> None:
    client = _client(monkeypatch, [LLMError("network down")])
    agent = DialogueAgent(llm=client)
    result = await agent.handle("I need a commercial RO system for my hotel")
    assert client.attempts >= 1  # the LLM was actually tried
    assert result.asked_slot == "capacity"
    assert "capacity" in result.reply.lower()
    assert "hotel" in result.reply.lower()  # deterministic fallback still contextual


@pytest.mark.asyncio
async def test_agent_uses_llm_reply_when_it_works(monkeypatch) -> None:
    polished = "Sure, how many litres per hour do you need for the hotel?"
    client = _client(monkeypatch, [polished])
    agent = DialogueAgent(llm=client)
    result = await agent.handle("I need a commercial RO system for my hotel")
    assert result.reply == polished
    assert client.attempts == 1  # used on the first try, no retry


@pytest.mark.asyncio
async def test_agent_rejects_llm_reply_that_breaks_the_voice_contract(
    monkeypatch,
) -> None:
    """No question mark while a slot is pending → keep the deterministic reply."""
    client = _client(monkeypatch, ["Sure thing, we will get to that later today"])
    agent = DialogueAgent(llm=client)
    result = await agent.handle("I need a commercial RO system for my hotel")
    assert "capacity" in result.reply.lower()  # fallback kept


@pytest.mark.asyncio
async def test_agent_never_calls_llm_when_no_key(monkeypatch) -> None:
    agent = DialogueAgent(llm=LLMClient(api_key=""))
    result = await agent.handle("I need a commercial RO system for my hotel")
    assert result.asked_slot == "capacity"


# ── summary falls back to rule-based (D19 summary fallback) ──────────────────
_VALID_SUMMARY_JSON = json.dumps(
    {
        "summary": "LLM summary of the call.",
        "key_requirements": ["capacity: 500 LPH"],
        "customer_intent": "Buy a RO system",
        "important_points": ["Bangalore site"],
        "followup_actions": ["Send quote"],
        "outcome": "interested",
        "lead_status": "hot",
        "followup_required": True,
    }
)

_SLOTS = {"requirement": "commercial RO for hotel", "capacity": "500 LPH"}
_TRANSCRIPT = ["customer: I need a commercial RO", "agent: What capacity?"]


@pytest.mark.asyncio
async def test_summary_uses_llm_when_json_is_valid(monkeypatch) -> None:
    client = _client(monkeypatch, [_VALID_SUMMARY_JSON])
    data, source = await generate_summary(client, _SLOTS, _TRANSCRIPT)
    assert source == "llm"
    assert data.summary == "LLM summary of the call."
    assert data.outcome.value == "interested"


@pytest.mark.asyncio
async def test_summary_falls_back_when_llm_returns_bad_json(monkeypatch) -> None:
    client = _client(monkeypatch, ["not json at all"])
    data, source = await generate_summary(client, _SLOTS, _TRANSCRIPT)
    assert source == "rule_based"
    assert client.attempts == 3  # retries happened before falling back
    # fallback still satisfies the full contract
    CallSummaryCreate.model_validate(data.model_dump())


@pytest.mark.asyncio
async def test_summary_falls_back_when_llm_json_is_incomplete(monkeypatch) -> None:
    client = _client(monkeypatch, [json.dumps({"summary": "only a summary"})])
    data, source = await generate_summary(client, _SLOTS, _TRANSCRIPT)
    assert source == "rule_based"
    assert data.followup_actions  # deterministic content present


@pytest.mark.asyncio
async def test_summary_falls_back_when_llm_raises(monkeypatch) -> None:
    client = _client(monkeypatch, [LLMError("hard failure")])
    data, source = await generate_summary(client, _SLOTS, _TRANSCRIPT)
    assert source == "rule_based"
    assert client.attempts == 3
    assert data.outcome.value in {"interested", "incomplete", "not_interested"}


@pytest.mark.asyncio
async def test_summary_without_llm_is_immediately_rule_based() -> None:
    data, source = await generate_summary(None, _SLOTS, _TRANSCRIPT)
    assert source == "rule_based"
    assert data.summary
