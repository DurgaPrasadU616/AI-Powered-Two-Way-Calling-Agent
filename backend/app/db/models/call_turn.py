"""CallTurn ORM model — one row per speaker turn in a call."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, Text, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.enums import Speaker

if TYPE_CHECKING:
    from app.db.models.call import Call


class CallTurn(Base):
    __tablename__ = "call_turns"
    __table_args__ = (
        # Composite index for fetching an ordered transcript efficiently
        Index("ix_call_turns_call_id_turn_index", "call_id", "turn_index"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    call_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("calls.id", ondelete="CASCADE"), nullable=False
    )
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)
    speaker: Mapped[Speaker] = mapped_column(
        SAEnum(Speaker, name="speaker_type", create_type=False), nullable=False
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    call: Mapped[Call] = relationship("Call", back_populates="turns")

    def __repr__(self) -> str:
        return (
            f"<CallTurn call={self.call_id} turn={self.turn_index} "
            f"speaker={self.speaker.value!r}>"
        )
