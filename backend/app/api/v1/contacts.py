"""Contact routes — full CRUD, E.164 validated, auth-protected."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.models.admin import Admin
from app.db.models.call import Call
from app.db.models.contact import Contact
from app.db.session import get_db
from app.schemas.contact import ContactCreate, ContactRead, ContactUpdate

router = APIRouter(prefix="/contacts", tags=["contacts"])


@router.get("", response_model=list[ContactRead], summary="List contacts")
async def list_contacts(
    q: str | None = Query(default=None, description="name/company search fragment"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _: Admin = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[Contact]:
    stmt = select(Contact)
    if q:
        stmt = stmt.where(
            Contact.name.ilike(f"%{q}%") | func.coalesce(Contact.company, "").ilike(f"%{q}%")
        )
    stmt = stmt.order_by(Contact.id).offset((page - 1) * page_size).limit(page_size)
    return list((await session.scalars(stmt)).all())


@router.post("", response_model=ContactRead, status_code=201, summary="Create contact")
async def create_contact(
    payload: ContactCreate,
    _: Admin = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> Contact:
    contact = Contact(**payload.model_dump())
    session.add(contact)
    await session.flush()
    return contact


@router.get("/{contact_id}", response_model=ContactRead, summary="Get one contact")
async def get_contact(
    contact_id: int,
    _: Admin = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> Contact:
    contact = await session.get(Contact, contact_id)
    if contact is None:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact


@router.patch("/{contact_id}", response_model=ContactRead, summary="Update contact")
async def update_contact(
    contact_id: int,
    payload: ContactUpdate,
    _: Admin = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> Contact:
    contact = await session.get(Contact, contact_id)
    if contact is None:
        raise HTTPException(status_code=404, detail="Contact not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(contact, key, value)
    await session.flush()
    return contact


@router.delete("/{contact_id}", status_code=204, summary="Delete contact")
async def delete_contact(
    contact_id: int,
    _: Admin = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> Response:
    contact = await session.get(Contact, contact_id)
    if contact is None:
        raise HTTPException(status_code=404, detail="Contact not found")
    await session.execute(update(Call).where(Call.contact_id == contact_id).values(contact_id=None))
    await session.delete(contact)
    await session.flush()
    return Response(status_code=204)
