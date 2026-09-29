"""Import all ORM models so they register with Base.metadata before Alembic runs."""

from app.db.models.admin import Admin
from app.db.models.call import Call
from app.db.models.call_event import CallEvent
from app.db.models.call_extracted_data import CallExtractedData
from app.db.models.call_summary import CallSummary
from app.db.models.call_turn import CallTurn
from app.db.models.contact import Contact

__all__ = [
    "Admin",
    "Contact",
    "Call",
    "CallTurn",
    "CallExtractedData",
    "CallSummary",
    "CallEvent",
]
