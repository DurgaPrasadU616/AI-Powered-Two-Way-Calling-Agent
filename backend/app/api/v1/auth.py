"""Auth routes — POST /auth/login with brute-force protection."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, login_rate_limit
from app.core.config import get_settings
from app.core.security import create_access_token, verify_password
from app.db.models.admin import Admin
from app.db.session import get_db
from app.schemas.auth import LoginRequest, TokenResponse

router = APIRouter(prefix="/auth")
settings = get_settings()


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Exchange admin credentials for a JWT",
)
async def login(
    credentials: LoginRequest,
    _: None = Depends(login_rate_limit),
    session: AsyncSession = Depends(get_db),
) -> TokenResponse:
    admin = await session.scalar(select(Admin).where(Admin.email == credentials.email))
    if admin is None:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    valid = await asyncio.to_thread(verify_password, credentials.password, admin.password_hash)
    if not valid:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_access_token(admin.email)
    return TokenResponse(
        access_token=token,
        expires_in=settings.JWT_EXPIRE_MINUTES * 60,
    )


@router.get("/me", summary="Identity of the calling admin")
async def me(admin: Admin = Depends(get_current_user)) -> dict[str, str]:
    return {"email": admin.email}
