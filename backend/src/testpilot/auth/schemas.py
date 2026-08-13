"""Request/response schemas for the Auth API (contracts/auth-api.md)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

_MIN_PASSWORD_LENGTH = 10


def _validate_password_strength(password: str) -> str:
    if len(password) < _MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {_MIN_PASSWORD_LENGTH} characters long")
    return password


class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    name: str = Field(min_length=1, max_length=200)

    _validate_password = field_validator("password")(_validate_password_strength)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

    _validate_password = field_validator("new_password")(_validate_password_strength)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    _validate_password = field_validator("new_password")(_validate_password_strength)


class UpdateProfileRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    email: EmailStr | None = None


class UserPublic(BaseModel):
    id: uuid.UUID
    email: str
    name: str
    created_at: datetime


class OrganizationPublic(BaseModel):
    id: uuid.UUID
    name: str
    slug: str


class SignupResponse(BaseModel):
    user: UserPublic
    organization: OrganizationPublic
    access_token: str


class LoginResponse(BaseModel):
    user: UserPublic
    access_token: str


class RefreshResponse(BaseModel):
    access_token: str


class MeResponse(BaseModel):
    user: UserPublic
    organization: OrganizationPublic
    role: str


class SessionPublic(BaseModel):
    id: uuid.UUID
    created_at: datetime
    last_used_at: datetime | None
    is_current: bool


class SessionsListResponse(BaseModel):
    items: list[SessionPublic]
