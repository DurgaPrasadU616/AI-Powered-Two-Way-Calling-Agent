"""CallSummary ORM model — post-call AI-generated summary."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Text, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.enums import CallOutcome, LeadStatus

if TYPE_CHECKING:
    from app.db.models.call import Call


class CallSummary(Base):
    __tablename__ = "call_summaries"

    call_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("calls.id", ondelete="CASCADE"), primary_key=True
    )
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    key_requirements: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    customer_intent: Mapped[str | None] = mapped_column(Text, nullable=True)
    important_points: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    followup_actions: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    outcome: Mapped[CallOutcome | None] = mapped_column(
        # Reuse the PostgreSQL enum type already created for calls
        SAEnum(CallOutcome, name="call_outcome", create_type=False),
        nullable=True,
    )
    lead_status: Mapped[LeadStatus | None] = mapped_column(
        SAEnum(LeadStatus, name="lead_status", create_type=False),
        nullable=True,
    )
    followup_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    call: Mapped[Call] = relationship("Call", back_populates="summary")

    def __repr__(self) -> str:
        return f"<CallSummary call={self.call_id} outcome={self.outcome}>"
