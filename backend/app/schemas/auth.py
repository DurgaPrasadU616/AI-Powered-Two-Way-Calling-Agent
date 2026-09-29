"""Auth schemas — login request and token response."""

from __future__ import annotations

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """Credentials posted to /auth/login."""

    email: str = Field(min_length=3, max_length=255, examples=["admin@sephawk.com"])
    password: str = Field(min_length=1, max_length=256)


class TokenResponse(BaseModel):
    """Successful login payload."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
