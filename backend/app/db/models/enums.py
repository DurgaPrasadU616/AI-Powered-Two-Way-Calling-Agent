"""All application enums — single source of truth for Python and PostgreSQL."""

from __future__ import annotations

import enum


class CallStatus(enum.StrEnum):
    queued = "queued"
    ringing = "ringing"
    in_progress = "in_progress"
    completed = "completed"
    no_answer = "no_answer"
    failed = "failed"
    disconnected = "disconnected"
    invalid_number = "invalid_number"


class CallOutcome(enum.StrEnum):
    interested = "interested"
    not_interested = "not_interested"
    callback_requested = "callback_requested"
    no_response = "no_response"
    failed = "failed"
    incomplete = "incomplete"


class CallDirection(enum.StrEnum):
    outbound = "outbound"


class CallProviderType(enum.StrEnum):
    browser = "browser"
    twilio = "twilio"


class LeadStatus(enum.StrEnum):
    hot = "hot"
    warm = "warm"
    cold = "cold"
    interested = "interested"
    not_interested = "not_interested"
    unknown = "unknown"


class Speaker(enum.StrEnum):
    customer = "customer"
    agent = "agent"
    system = "system"
