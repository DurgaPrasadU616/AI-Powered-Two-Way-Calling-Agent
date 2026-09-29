"""Slot definitions and state — the structured data the agent must collect.

Order matters: it is both the ask order and the "next missing slot" order.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Ask order (required slots only — the call is not complete until all are filled)
REQUIRED_SLOTS: tuple[str, ...] = (
    "requirement",
    "capacity",
    "location",
    "budget",
    "timeline",
    "customer_name",
)

# Optional enrichment slots — never asked directly, captured opportunistically
OPTIONAL_SLOTS: tuple[str, ...] = ("company", "application", "additional_requirements")

# Slot name → call_extracted_data column
DB_COLUMNS: dict[str, str] = {
    "requirement": "requirement",
    "capacity": "ro_capacity_lph",
    "location": "location",
    "budget": "budget",
    "timeline": "timeline",
    "customer_name": "customer_name",
    "company": "company_name",
    "application": "application",
    "additional_requirements": "additional_requirements",
}

# Single-question prompts — voice-friendly, one sentence, no markdown
QUESTIONS: dict[str, str] = {
    "requirement": "Can you tell me what you're looking for?",
    "capacity": "And what capacity do you need{context}?",
    "location": "Where do you need it installed?",
    "budget": "And what budget did you have in mind?",
    "timeline": "By when do you need it?",
    "customer_name": "May I know your name?",
}

# Application keywords detected in the opening requirement text
APPLICATION_KEYWORDS: dict[str, str] = {
    "hotel": "hotel",
    "restaurant": "restaurant",
    "factory": "factory",
    "plant": "plant",
    "school": "school",
    "college": "college",
    "apartment": "apartment",
    "office": "office",
    "cafe": "cafe",
    "canteen": "canteen",
    "hospital": "hospital",
    "hostel": "hostel",
    "dairy": "dairy",
    "pharma": "pharma",
}

# Nouns used to reference earlier context inside later questions
_CONTEXT_PHRASES: dict[str, str] = {
    "hotel": "for the hotel",
    "restaurant": "for the restaurant",
    "factory": "for the factory",
    "plant": "for the plant",
    "school": "for the school",
    "college": "for the college",
    "apartment": "for the apartment",
    "office": "for the office",
    "cafe": "for the cafe",
    "canteen": "for the canteen",
    "hospital": "for the hospital",
    "hostel": "for the hostel",
    "dairy": "for the dairy",
    "pharma": "for the pharma unit",
}


def detect_application(text: str) -> str | None:
    """Return the application keyword found in *text* (e.g. ``"hotel"``)."""
    lowered = text.lower()
    for keyword in APPLICATION_KEYWORDS:
        if keyword in lowered:
            return keyword
    return None


def context_reference(requirement: str | None, application: str | None = None) -> str:
    """Return ``" for the hotel"`` style fragment, or ``""`` when unknown."""
    key = application or detect_application(requirement or "")
    if key and key in _CONTEXT_PHRASES:
        return " " + _CONTEXT_PHRASES[key]
    return ""


def question_for(slot: str, requirement: str | None = None, application: str | None = None) -> str:
    """Render the one-sentence question for *slot*, including context reference."""
    template = QUESTIONS[slot]
    return template.format(context=context_reference(requirement, application))


@dataclass
class SlotState:
    """Mutable slot container.

    Hard rule (audit D17d): a filled slot is **never** overwritten with
    ``None``/empty — :meth:`set` silently ignores those writes.
    """

    values: dict[str, str | None] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for slot in (*REQUIRED_SLOTS, *OPTIONAL_SLOTS):
            self.values.setdefault(slot, None)

    def is_filled(self, slot: str) -> bool:
        value = self.values.get(slot)
        return value is not None and bool(str(value).strip())

    def set(self, slot: str, value: str | None) -> bool:
        """Fill *slot*; refuse empty values and never clobber a filled slot."""
        if value is None:
            return False
        cleaned = str(value).strip()
        if not cleaned:
            return False
        if self.is_filled(slot):
            return False
        self.values[slot] = cleaned
        return True

    def force_set(self, slot: str, value: str | None) -> bool:
        """Overwrite even a filled slot (only ever called with non-empty values)."""
        if value is None or not str(value).strip():
            return False
        self.values[slot] = str(value).strip()
        return True

    @property
    def filled(self) -> dict[str, str]:
        return {k: v for k, v in self.values.items() if v}

    @property
    def missing_required(self) -> list[str]:
        return [slot for slot in REQUIRED_SLOTS if not self.is_filled(slot)]

    @property
    def all_required_filled(self) -> bool:
        return not self.missing_required

    def next_missing(self) -> str | None:
        """First unfilled required slot in ask order."""
        for slot in REQUIRED_SLOTS:
            if not self.is_filled(slot):
                return slot
        return None

    def as_dict(self) -> dict[str, str | None]:
        return dict(self.values)
