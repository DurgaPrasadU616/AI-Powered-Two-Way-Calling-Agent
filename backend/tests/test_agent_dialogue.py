"""Agent behaviour tests — audit checks D17 (a)–(h) plus extraction edge cases."""

from __future__ import annotations

import pytest
from app.agent.dialogue import DialogueAgent, Phase
from app.agent.slots import REQUIRED_SLOTS, SlotState

SCRIPT = [
    "I need a commercial RO system for my hotel",
    "500 LPH",
    "Bangalore",
    "around 1 lakh",
    "within a month",
    "my name is Rahul Kumar",
]


async def _run(turns: list[str], agent: DialogueAgent | None = None):
    agent = agent or DialogueAgent()
    results = []
    for turn in turns:
        results.append(await agent.handle(turn))
    return agent, results


def _markdownish(reply: str) -> bool:
    return any(marker in reply for marker in ("*", "#", "`", "\n", "- ", "1. "))


# (a) one question at a time ───────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_a_one_question_at_a_time() -> None:
    _, results = await _run(SCRIPT)
    for result in results:
        assert result.reply.count("?") <= 1, f"multiple questions: {result.reply!r}"
        assert result.reply.count("?") >= 0
    # every gathering turn asks exactly one question
    for result in results[:-1]:
        assert result.reply.count("?") == 1, f"no question asked: {result.reply!r}"


# (b) never re-asks a filled slot ──────────────────────────────────────────────
@pytest.mark.asyncio
async def test_b_never_reasks_a_filled_slot() -> None:
    agent = DialogueAgent()
    asked_order: list[str] = []
    for utterance in SCRIPT:
        filled_before = {k for k, v in agent.slots.as_dict().items() if v}
        result = await agent.handle(utterance)
        if result.asked_slot is not None:
            assert (
                result.asked_slot not in filled_before
            ), f"re-asked filled slot {result.asked_slot!r}"
            asked_order.append(result.asked_slot)
        # nothing previously filled disappeared
        for slot in filled_before:
            assert agent.slots.is_filled(slot), f"filled slot {slot!r} lost"
    assert asked_order == [
        "capacity",
        "location",
        "budget",
        "timeline",
        "customer_name",
    ]


# (c) references earlier context ───────────────────────────────────────────────
@pytest.mark.asyncio
async def test_c_references_earlier_context() -> None:
    _, results = await _run(SCRIPT)
    # capacity question must reference the hotel from turn 1
    assert "hotel" in results[0].reply.lower(), results[0].reply
    # closing must use the name collected in the last turn
    assert "Rahul Kumar" in results[-1].reply


# (d) filled slot never overwritten with null ──────────────────────────────────
def test_d_slot_state_refuses_null_and_clobber() -> None:
    state = SlotState()
    assert state.set("capacity", "500 LPH") is True
    assert state.set("capacity", None) is False  # null write refused
    assert state.set("capacity", "  ") is False  # empty write refused
    assert state.set("capacity", "1000 LPH") is False  # clobber refused
    assert state.values["capacity"] == "500 LPH"


@pytest.mark.asyncio
async def test_d_filled_slot_survives_unparsable_message() -> None:
    agent = DialogueAgent()
    await agent.handle(SCRIPT[0])  # requirement filled, pending=capacity
    await agent.handle(SCRIPT[1])  # capacity filled, pending=location
    # long, unparsable ramble → must not touch capacity or location
    await agent.handle(
        "I was just wondering whether you also handle water softeners and "
        "other kinds of filtration equipment for other purposes as well"
    )
    assert agent.slots.values["capacity"] == "500 LPH"
    assert agent.slots.values["requirement"] == "a commercial RO system for my hotel"
    assert agent.slots.values["location"] is None  # not filled with garbage either


# (e) customer question answered, then back to the next missing slot ───────────
@pytest.mark.asyncio
async def test_e_question_answered_then_returns_to_slot() -> None:
    agent = DialogueAgent()
    await agent.handle(SCRIPT[0])  # pending = capacity
    result = await agent.handle("Do you provide installation?")
    reply = result.reply.lower()
    assert "installation" in reply or "install" in reply, result.reply  # answered
    assert "?" in result.reply  # then continues the flow
    assert result.asked_slot == "capacity"  # back to the same missing slot
    assert agent.slots.values["capacity"] is None  # nothing filled by the question
    # flow continues normally afterwards
    followup = await agent.handle("500 LPH")
    assert agent.slots.values["capacity"] == "500 LPH"
    assert followup.asked_slot == "location"


# (f) "not interested" → WRAP_UP ───────────────────────────────────────────────
@pytest.mark.asyncio
async def test_f_not_interested_goes_to_wrap_up() -> None:
    agent = DialogueAgent()
    result = await agent.handle("I'm not interested, please don't call again")
    assert agent.phase == Phase.WRAP_UP
    assert result.state == "WRAP_UP"
    assert agent.not_interested is True
    assert agent.slots.all_required_filled is False  # stopped early
    # next customer turn ends the conversation
    nxt = await agent.handle("ok bye")
    assert nxt.state == "ENDED"


# (g) short, voice-friendly replies ────────────────────────────────────────────
@pytest.mark.asyncio
async def test_g_replies_are_short_and_voice_friendly() -> None:
    agent = DialogueAgent()
    turns = SCRIPT + ["Do you provide installation?", "sure, thanks", "ok bye"]
    for utterance in turns:
        result = await agent.handle(utterance)
        reply = result.reply
        assert len(reply) <= 320, f"too long ({len(reply)}): {reply!r}"
        assert "\n" not in reply, f"multi-line reply: {reply!r}"
        assert not _markdownish(reply), f"markdown in reply: {reply!r}"
        assert reply.count("?") <= 1


# (h) conversation ends after all slots filled ─────────────────────────────────
@pytest.mark.asyncio
async def test_h_ends_after_all_slots_filled() -> None:
    agent, results = await _run(SCRIPT)
    assert agent.slots.all_required_filled
    assert results[-1].state == "WRAP_UP"
    assert results[-1].ended is False  # WRAP_UP announced, next turn closes
    after = await agent.handle("thanks, bye")
    assert after.state == "ENDED"
    # slots are frozen once the call is over
    frozen = dict(agent.slots.as_dict())
    await agent.handle("actually my budget is 10 rupees")
    assert agent.slots.as_dict() == frozen


# ── extraction & flow extras ──────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_slot_values_match_the_script() -> None:
    agent, _ = await _run(SCRIPT)
    values = agent.slots.as_dict()
    assert values["requirement"] == "a commercial RO system for my hotel"
    assert values["capacity"] == "500 LPH"
    assert values["location"] == "Bangalore"
    assert values["budget"] == "around 1 lakh"
    assert values["timeline"] == "within a month"
    assert values["customer_name"] == "Rahul Kumar"
    assert values["application"] == "hotel"


@pytest.mark.asyncio
async def test_greeting_first_gets_the_requirement_question() -> None:
    agent = DialogueAgent()
    result = await agent.handle("hello")
    assert "?" in result.reply
    assert result.asked_slot == "requirement"


@pytest.mark.asyncio
async def test_missing_required_order_is_stable() -> None:
    agent = DialogueAgent()
    await agent.handle(SCRIPT[0])
    assert agent.slots.next_missing() == "capacity"
    for slot in REQUIRED_SLOTS:
        agent.slots.set(slot, "x")
    assert agent.slots.next_missing() is None
