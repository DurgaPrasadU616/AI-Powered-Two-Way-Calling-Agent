"""Pydantic schemas — one module per resource."""

from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.call import (
    CallCreate,
    CallDetailRead,
    CallEventRead,
    CallListResponse,
    CallRead,
    CallTurnRead,
    ExtractedDataRead,
    PageMeta,
    SummaryRead,
)
from app.schemas.contact import ContactCreate, ContactRead, ContactUpdate
from app.schemas.dashboard import DashboardStats

__all__ = [
    "LoginRequest",
    "TokenResponse",
    "ContactCreate",
    "ContactUpdate",
    "ContactRead",
    "CallCreate",
    "CallRead",
    "CallListResponse",
    "CallDetailRead",
    "CallTurnRead",
    "ExtractedDataRead",
    "SummaryRead",
    "CallEventRead",
    "PageMeta",
    "DashboardStats",
]
