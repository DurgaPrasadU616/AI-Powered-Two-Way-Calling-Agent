"""Seed database with initial admin + contacts.

Run from backend/ directory after `alembic upgrade head`:
    python scripts/seed_db.py

Uses the same bcrypt helpers as the app so the hash is guaranteed correct.
"""

from __future__ import annotations

import asyncio
import sys

# Ensure app is importable when run from backend/
sys.path.insert(0, ".")

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.models.admin import Admin
from app.db.models.contact import Contact
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

settings = get_settings()

_CONTACTS = [
    {
        "name": "Rahul Kumar",
        "phone_e164": "+919876543210",
        "company": "Hotel Blue Diamond",
        "purpose": "Interested in commercial RO system for hotel water treatment",
        "product": "Commercial RO System",
    },
    {
        "name": "Priya Sharma",
        "phone_e164": "+919845123456",
        "company": "Sharma Food Industries",
        "purpose": "Enquiry about industrial RO system for food processing plant",
        "product": "Industrial RO System",
    },
]

_ADMIN = {
    "email": settings.ADMIN_EMAIL,
    "password": settings.ADMIN_PASSWORD,
}


async def seed(session: AsyncSession) -> None:
    # Admin
    existing_admin = await session.scalar(select(Admin).where(Admin.email == _ADMIN["email"]))
    if existing_admin is None:
        admin = Admin(
            email=_ADMIN["email"],
            password_hash=hash_password(_ADMIN["password"]),
        )
        session.add(admin)
        print(f"  ✓ Admin created: {_ADMIN['email']} (password from ADMIN_PASSWORD env)")
    else:
        print(f"  · Admin already exists: {_ADMIN['email']}")

    # Contacts
    for data in _CONTACTS:
        existing = await session.scalar(
            select(Contact).where(Contact.phone_e164 == data["phone_e164"])
        )
        if existing is None:
            contact = Contact(**data)
            session.add(contact)
            print(f"  ✓ Contact created: {data['name']} ({data['phone_e164']})")
        else:
            print(f"  · Contact already exists: {data['name']} ({data['phone_e164']})")

    await session.commit()
    print("\nSeeding complete.")


async def main() -> None:
    print(f"Connecting to: {settings.DATABASE_URL}\n")
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        await seed(session)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
