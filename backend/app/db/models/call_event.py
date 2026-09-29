"""CallEvent ORM model — lifecycle and error events for a call."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.call import Call


class CallEvent(Base):
    __tablename__ = "call_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    call_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("calls.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # e.g. no_answer | silence_timeout | stt_failure | llm_failure |
    #       interrupted | provider_error | disconnected | call_started | call_ended
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    detail: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    call: Mapped[Call] = relationship("Call", back_populates="events")

    def __repr__(self) -> str:
        return f"<CallEvent id={self.id} call={self.call_id} " f"type={self.event_type!r}>"
