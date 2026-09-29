"""Call ORM model — central table of the system."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.enums import (
    CallDirection,
    CallOutcome,
    CallProviderType,
    CallStatus,
    LeadStatus,
)

if TYPE_CHECKING:
    from app.db.models.call_event import CallEvent
    from app.db.models.call_extracted_data import CallExtractedData
    from app.db.models.call_summary import CallSummary
    from app.db.models.call_turn import CallTurn
    from app.db.models.contact import Contact


class Call(Base):
    __tablename__ = "calls"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contact_id: Mapped[int | None] = mapped_column(ForeignKey("contacts.id"), nullable=True)
    phone_number: Mapped[str] = mapped_column(String(20), nullable=False)
    direction: Mapped[CallDirection] = mapped_column(
        SAEnum(CallDirection, name="call_direction", create_type=False),
        nullable=False,
        default=CallDirection.outbound,
    )
    provider: Mapped[CallProviderType] = mapped_column(
        SAEnum(CallProviderType, name="call_provider", create_type=False),
        nullable=False,
        default=CallProviderType.browser,
    )
    provider_call_sid: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[CallStatus] = mapped_column(
        SAEnum(CallStatus, name="call_status", create_type=False),
        nullable=False,
        default=CallStatus.queued,
        index=True,
    )
    outcome: Mapped[CallOutcome | None] = mapped_column(
        SAEnum(CallOutcome, name="call_outcome", create_type=False),
        nullable=True,
        index=True,
    )
    start_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lead_status: Mapped[LeadStatus] = mapped_column(
        SAEnum(LeadStatus, name="lead_status", create_type=False),
        nullable=False,
        default=LeadStatus.unknown,
        index=True,
    )
    followup_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    contact: Mapped[Contact | None] = relationship("Contact", back_populates="calls")
    turns: Mapped[list[CallTurn]] = relationship(
        "CallTurn", back_populates="call", order_by="CallTurn.turn_index"
    )
    extracted_data: Mapped[CallExtractedData | None] = relationship(
        "CallExtractedData", back_populates="call", uselist=False
    )
    summary: Mapped[CallSummary | None] = relationship(
        "CallSummary", back_populates="call", uselist=False
    )
    events: Mapped[list[CallEvent]] = relationship(
        "CallEvent", back_populates="call", order_by="CallEvent.created_at"
    )

    def __repr__(self) -> str:
        return f"<Call id={self.id} status={self.status.value!r}>"
