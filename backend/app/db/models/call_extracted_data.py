"""CallExtractedData ORM model — live slot data updated during the call."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.call import Call


class CallExtractedData(Base):
    __tablename__ = "call_extracted_data"

    call_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("calls.id", ondelete="CASCADE"), primary_key=True
    )
    # Slots extracted by the agent planner
    customer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    requirement: Mapped[str | None] = mapped_column(Text, nullable=True)
    ro_capacity_lph: Mapped[str | None] = mapped_column(String(100), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    application: Mapped[str | None] = mapped_column(String(255), nullable=True)
    budget: Mapped[str | None] = mapped_column(String(255), nullable=True)
    timeline: Mapped[str | None] = mapped_column(String(255), nullable=True)
    additional_requirements: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Full raw LLM extraction JSON kept for debugging / reprocessing
    raw_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    call: Mapped[Call] = relationship("Call", back_populates="extracted_data")

    def __repr__(self) -> str:
        return f"<CallExtractedData call={self.call_id}>"
