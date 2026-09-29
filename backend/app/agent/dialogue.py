"""Dialogue state machine — the agent's turn-by-turn brain.

Deterministic core (slot filling, intent, question selection) with optional
LLM phrasing layered on top. The deterministic reply is always computed
first, so an LLM failure degrades to a correct, voice-friendly fallback
instead of breaking the conversation (audit D19).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum

from app.agent.llm import LLMClient, LLMError
from app.agent.slots import (
    REQUIRED_SLOTS,
    SlotState,
    detect_application,
    question_for,
)
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


# ── States ────────────────────────────────────────────────────────────────────
class Phase(StrEnum):
    GATHERING = "GATHERING"
    WRAP_UP = "WRAP_UP"
    ENDED = "ENDED"


# ── Intent patterns ───────────────────────────────────────────────────────────
_NOT_INTERESTED_RE = re.compile(
    r"\b(not interested|not now|no thanks|no thank you|do not want|don't want|"
    r"not looking for|stop calling|remove (my|me) (number|from)|not required|"
    r"already have|not worth)\b",
    re.IGNORECASE,
)

_QUESTION_RE = re.compile(
    r"\?\s*$|^\s*(what|how|when|where|why|who|which|can you|could you|do you|does|"
    r"are there|is there|is it|will you|would you|tell me|price|cost|how much)",
    re.IGNORECASE,
)

_GREETING_RE = re.compile(
    r"^\s*(hi|hello|hey|good (morning|afternoon|evening)|namaste)\b[.!]?\s*$",
    re.IGNORECASE,
)

# "I need a commercial RO system" → "a commercial RO system"
_REQUIREMENT_PREFIX_RE = re.compile(
    r"^\s*(?:i(?:'m| am)?\s+)?(?:need|want|looking for|require|searching for|interested in)\s+",
    re.IGNORECASE,
)

_NAME_RE = re.compile(
    r"\b(?:my name is|i am|i'm|this is|it's|name's|here)\s+([A-Za-z][A-Za-z .'-]{1,40})",
    re.IGNORECASE,
)

_CAPACITY_RE = re.compile(r"\b\d[\d,.]*\s*(?:lph|litres?|liters?|lpm|kl|kld)\b", re.IGNORECASE)
_TIMELINE_RE = re.compile(
    r"\b(within|in|by|after|before|next|this)\b|\b(day|days|week|weeks|month|months|"
    r"year|years|asap|immediately)\b",
    re.IGNORECASE,
)
_BUDGET_RE = re.compile(
    r"\b(lakh|lakhs|crore|crores|rupees|rs\.?|inr|k\b|thousand|budget)\b|\d",
    re.IGNORECASE,
)

# ── Canned answers for common mid-flow questions (fallback path) ──────────────
_ANSWER_BANK: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"\b(install|installation|setup|commission)\w*\b", re.IGNORECASE),
        "Yes, we handle delivery, installation and commissioning end to end.",
    ),
    (
        re.compile(r"\b(warranty|guarantee)\w*\b", re.IGNORECASE),
        "We give a one year warranty with annual service contracts.",
    ),
    (
        re.compile(r"\b(price|pricing|cost|how much|quote|quotation)\w*\b", re.IGNORECASE),
        "Pricing depends on the capacity and membrane selection, and I'll get you a exact quote after this call.",
    ),
    (
        re.compile(r"\b(deliver|delivery|lead time|how long to)\w*\b", re.IGNORECASE),
        "Standard delivery is two to three weeks from order confirmation.",
    ),
    (
        re.compile(r"\b(service|maintain|maintenance|amc|support|repair)\w*\b", re.IGNORECASE),
        "We offer annual maintenance contracts with round the clock support.",
    ),
    (
        re.compile(r"\b(purif|quality|mineral|ph|taste)\w*\b", re.IGNORECASE),
        "The system removes impurities while keeping the water clean and safe to use.",
    ),
]

_GENERIC_ANSWER = (
    "That's a fair question, and I'll cover it in detail when I send you the information "
    "after this call."
)

# ── Closings ──────────────────────────────────────────────────────────────────
_CLOSING_ALL_FILLED = (
    "Thanks {name}, that's everything I needed. I'll send over the details and the "
    "quote shortly. Have a great day!"
)
_CLOSING_NOT_INTERESTED = (
    "Understood, thanks for your time. I won't call you again. Have a good day!"
)
_CLOSING_BYE = "Thanks {name}, we're all done here. Goodbye!"


@dataclass
class AgentTurn:
    """Everything the caller (CLI / WebSocket session) needs for one turn."""

    reply: str
    phase: Phase
    slots: dict[str, str | None]
    pending_slot: str | None
    asked_slot: str | None
    ended: bool
    state: str = "GATHERING"
    extra: dict = field(default_factory=dict)


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def _title_case_name(raw: str) -> str:
    cleaned = _clean(raw).strip(" .,!?")
    return cleaned.title()


class DialogueAgent:
    """Slot-filling conversational agent (audit D17 a–h)."""

    def __init__(self, llm: LLMClient | None = None) -> None:
        self.llm = llm
        self.phase = Phase.GATHERING
        self.slots = SlotState()
        self.pending_slot: str | None = None
        self.last_asked_slot: str | None = None
        self.not_interested = False
        self.last_llm_error: str | None = None

    # ── helpers ──────────────────────────────────────────────────────────────
    @classmethod
    def from_settings(cls) -> DialogueAgent:
        from app.agent.llm import get_llm

        return cls(llm=get_llm())

    @property
    def ended(self) -> bool:
        return self.phase in (Phase.WRAP_UP, Phase.ENDED)

    def _requirement(self) -> str | None:
        return self.slots.values.get("requirement")

    def _application(self) -> str | None:
        return self.slots.values.get("application")

    def _question_for(self, slot: str) -> str:
        return question_for(slot, self._requirement(), self._application())

    def _name(self) -> str:
        return self.slots.values.get("customer_name") or "there"

    # ── extraction ───────────────────────────────────────────────────────────
    def _extract_for_pending(self, slot: str, text: str) -> str | None:
        """Derive the value for *slot* from an answer-shaped message."""
        cleaned = _clean(text)
        if not cleaned:
            return None
        if slot == "customer_name":
            match = _NAME_RE.search(cleaned)
            if match:
                return _title_case_name(match.group(1))
            if len(cleaned.split()) <= 4 and not cleaned.endswith("?"):
                return _title_case_name(cleaned)
            return None
        if slot == "capacity":
            match = _CAPACITY_RE.search(cleaned)
            if match:
                return (
                    _clean(match.group(0)).upper().replace("LITRES", "LPH").replace("LITERS", "LPH")
                )
            return cleaned if len(cleaned.split()) <= 6 and not cleaned.endswith("?") else None
        if len(cleaned.split()) > 12 or cleaned.endswith("?"):
            return None
        return cleaned

    def _opportunistic_fill(self, text: str) -> None:
        """Fill slots from a message that wasn't a pending-slot answer."""
        # Name announced out of sequence: "my name is Rahul Kumar"
        if not self.slots.is_filled("customer_name"):
            match = _NAME_RE.search(text)
            if match and len(match.group(1).split()) <= 5:
                self.slots.set("customer_name", _title_case_name(match.group(1)))
        # Opening requirement (only once, and never a bare greeting)
        if not self.slots.is_filled("requirement") and len(text.split()) >= 3:
            requirement = _REQUIREMENT_PREFIX_RE.sub("", _clean(text), count=1)
            requirement = requirement.strip() or _clean(text)
            written = self.slots.set("requirement", requirement)
            application = detect_application(requirement) if written else None
            if application:
                self.slots.set("application", application)

        # Corrections to previously collected values ("actually 1000 LPH", "make it 1000 LPH")
        if re.search(r"\b(actually|correction|change (?:that|it) to|instead of|make it)\b", text, re.I):
            cap_m = _CAPACITY_RE.search(text)
            if cap_m:
                new_cap = _clean(cap_m.group(0)).upper().replace("LITRES", "LPH").replace("LITERS", "LPH")
                self.slots.force_set("capacity", new_cap)
            name_m = _NAME_RE.search(text)
            if name_m:
                self.slots.force_set("customer_name", _title_case_name(name_m.group(1)))

    async def _run_llm_extraction(self, text: str) -> None:
        """Extract slots via LLM with strict JSON schema and merge into state."""
        if self.llm is None or not self.llm.available or settings.SIMULATE_FAILURE == "llm":
            return
        from app.agent.extractor import extract_slots_llm

        extracted = await extract_slots_llm(self.llm, text, self.slots.values)
        if not extracted:
            return
        data = extracted.model_dump(exclude_none=True)
        is_corr = data.pop("is_correction", False)
        corr_slot = data.pop("corrected_slot", None)
        if is_corr and corr_slot and corr_slot in data:
            self.slots.force_set(corr_slot, data[corr_slot])
        for slot, val in data.items():
            if val and slot in self.slots.values:
                if is_corr:
                    self.slots.force_set(slot, str(val))
                else:
                    self.slots.set(slot, str(val))

    # ── replies ──────────────────────────────────────────────────────────────
    def _answer_question(self, text: str) -> str:
        for pattern, answer in _ANSWER_BANK:
            if pattern.search(text):
                return answer
        return _GENERIC_ANSWER

    def _fallback_reply(self, text: str) -> tuple[str, str | None]:
        """Deterministic reply: returns (reply, slot being asked | None)."""
        # 1. explicit opt-out
        if _NOT_INTERESTED_RE.search(text):
            self.phase = Phase.WRAP_UP
            self.not_interested = True
            self.pending_slot = None
            return _CLOSING_NOT_INTERESTED, None

        # 2. already wrapping up / ended
        if self.phase == Phase.WRAP_UP:
            self.phase = Phase.ENDED
            return _CLOSING_BYE.format(name=self._name()), None
        if self.phase == Phase.ENDED:
            return _CLOSING_BYE.format(name=self._name()), None

        # 3. customer question → answer, then return to the pending slot
        if _QUESTION_RE.search(text):
            answer = self._answer_question(text)
            target = self.pending_slot or self.slots.next_missing()
            if target is None:
                self.phase = Phase.WRAP_UP
                return f"{answer} {_CLOSING_ALL_FILLED.format(name=self._name())}", None
            self.pending_slot = target
            self.last_asked_slot = target
            return f"{answer} {self._question_for(target)}", target

        # 4. greeting before any requirement
        if _GREETING_RE.match(text) and not self.slots.is_filled("requirement"):
            self.pending_slot = "requirement"
            self.last_asked_slot = "requirement"
            return (
                "Hello! I'm calling from SERP Hawk about water treatment systems. "
                + self._question_for("requirement"),
                "requirement",
            )

        # 5. answer the pending slot
        if self.pending_slot:
            value = self._extract_for_pending(self.pending_slot, text)
            if value:
                self.slots.set(self.pending_slot, value)
                self.pending_slot = None
            else:
                # could not parse — ask again for the same slot
                self.last_asked_slot = self.pending_slot
                return (
                    f"Sorry, could you tell me that again? {self._question_for(self.pending_slot)}",
                    self.pending_slot,
                )

        # 6. catch anything useful mentioned unprompted
        self._opportunistic_fill(text)

        # 7. all required slots filled → wrap up
        if self.slots.all_required_filled:
            self.phase = Phase.WRAP_UP
            self.pending_slot = None
            self.last_asked_slot = None
            return _CLOSING_ALL_FILLED.format(name=self._name()), None

        # 8. ask the next missing slot (once)
        target = self.slots.next_missing()
        assert target is not None  # guarded by step 7
        self.pending_slot = target
        self.last_asked_slot = target
        return self._question_for(target), target

    def _llm_prompt(self, text: str) -> str:
        filled = (
            ", ".join(f"{slot}={value}" for slot, value in self.slots.filled.items())
            or "(none yet)"
        )
        missing = ", ".join(self.slots.missing_required) or "(none — wrap up)"
        return (
            "You are a polite outbound phone sales agent for commercial RO water "
            "treatment systems. Reply with ONE short spoken sentence, no lists, no "
            "markdown, no emoji, at most one question. Never re-ask a collected "
            "value.\n"
            f"Collected so far: {filled}\n"
            f"Still missing: {missing}\n"
            f"Reference earlier context naturally (e.g. 'for the hotel').\n"
            f"Customer said: {text!r}\n"
            "Your reply:"
        )

    async def _compose_reply(self, text: str) -> tuple[str, str | None]:
        """Deterministic reply first; optionally polish via LLM with fallback."""
        reply, asked_slot = self._fallback_reply(text)
        # closings/WRAP_UP are state-critical — always keep the deterministic text
        self.last_llm_error = None
        if settings.SIMULATE_FAILURE == "llm":
            self.last_llm_error = "Simulated LLM failure via SIMULATE_FAILURE=llm"
            logger.warning("Simulating LLM failure via SIMULATE_FAILURE=llm")
            return reply, asked_slot
        if self.llm is None or not self.llm.available or self.ended:
            return reply, asked_slot
        try:
            candidate = _clean(await self.llm.chat(self._llm_prompt(text)))
        except LLMError as exc:
            logger.warning("LLM reply failed, using fallback", extra={"error": str(exc)})
            self.last_llm_error = str(exc)
            return reply, asked_slot
        # guardrails: keep the voice contract no matter what the model says
        if not candidate or len(candidate) > 320 or candidate.count("?") > 1:
            return reply, asked_slot
        if asked_slot and "?" not in candidate:
            return reply, asked_slot
        return candidate, asked_slot

    # ── public API ───────────────────────────────────────────────────────────
    async def handle(self, user_text: str) -> AgentTurn:
        """Process one customer utterance and return the agent's turn."""
        text = _clean(user_text)
        await self._run_llm_extraction(text)
        reply, asked_slot = await self._compose_reply(text)
        return AgentTurn(
            reply=reply,
            phase=self.phase,
            slots=self.slots.as_dict(),
            pending_slot=self.pending_slot,
            asked_slot=asked_slot,
            ended=self.phase == Phase.ENDED,
            state=self.phase.value,
            extra={"not_interested": self.not_interested, "llm_error": self.last_llm_error},
        )


__all__ = ["DialogueAgent", "AgentTurn", "Phase", "REQUIRED_SLOTS"]
