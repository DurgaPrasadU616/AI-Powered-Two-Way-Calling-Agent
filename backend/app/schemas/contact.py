"""Contact schemas — E.164 phone validation is enforced at the schema level."""

from __future__ import annotations

from datetime import datetime

import phonenumbers
from pydantic import BaseModel, Field, field_validator


def validate_e164(value: str) -> str:
    """Return the normalised E.164 number or raise ValueError (→ HTTP 422)."""
    try:
        parsed = phonenumbers.parse(value, None)
    except phonenumbers.NumberParseException as exc:
        raise ValueError(f"invalid phone number: {value!r}") from exc
    if not phonenumbers.is_valid_number(parsed):
        raise ValueError(f"invalid phone number: {value!r}")
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)


class ContactBase(BaseModel):
    name: str = Field(min_length=1, max_length=255, examples=["Rahul Kumar"])
    phone_e164: str = Field(min_length=1, max_length=20, examples=["+919876543210"])
    company: str | None = Field(default=None, max_length=255, examples=["Hotel Blue Diamond"])
    purpose: str | None = Field(default=None, examples=["Commercial RO inquiry"])
    product: str | None = Field(default=None, max_length=255, examples=["Commercial RO 500 LPH"])

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "Rahul Kumar",
                "phone_e164": "+919876543210",
                "company": "Hotel Blue Diamond",
                "purpose": "Commercial RO inquiry",
                "product": "Commercial RO 500 LPH",
            }
        }
    }

    @field_validator("phone_e164")
    @classmethod
    def _phone_is_e164(cls, value: str) -> str:
        return validate_e164(value)


class ContactCreate(ContactBase):
    pass


class ContactUpdate(BaseModel):
    """Partial update — every field optional; phone re-validated when present."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    phone_e164: str | None = Field(default=None, max_length=20)
    company: str | None = Field(default=None, max_length=255)
    purpose: str | None = None
    product: str | None = Field(default=None, max_length=255)

    @field_validator("phone_e164")
    @classmethod
    def _phone_is_e164(cls, value: str | None) -> str | None:
        return None if value is None else validate_e164(value)


class ContactRead(ContactBase):
    id: int
    created_at: datetime

    model_config = {"from_attributes": True}
