import uuid
from datetime import datetime

from sqlalchemy import Column, Index
from sqlalchemy.dialects.postgresql import CITEXT
from sqlmodel import Field

from testpilot.core.models import BaseTable, tz_datetime_field


class User(BaseTable, table=True):
    """Not organization-scoped — a user's account exists independent of any
    one Organization; tenant scoping happens via Membership (data-model.md).
    """

    __tablename__ = "users"

    email: str = Field(sa_column=Column(CITEXT, unique=True, nullable=False))
    password_hash: str = Field(nullable=False)
    name: str = Field(nullable=False)
    is_active: bool = Field(default=True, nullable=False)
    last_login_at: datetime | None = tz_datetime_field()


class RefreshToken(BaseTable, table=True):
    """Session identity, not tenant data — no RLS policy (data-model.md)."""

    __tablename__ = "refresh_tokens"
    __table_args__ = (
        # "log out everywhere" (data-model.md): revoke every row for a user
        # WHERE user_id = ... AND revoked_at IS NULL.
        Index("ix_refresh_tokens_user_id_revoked_at", "user_id", "revoked_at"),
    )

    user_id: uuid.UUID = Field(foreign_key="users.id", nullable=False, index=True)
    token_hash: str = Field(sa_column_kwargs={"unique": True}, nullable=False)
    expires_at: datetime = tz_datetime_field(nullable=False)
    revoked_at: datetime | None = tz_datetime_field()
    last_used_at: datetime | None = tz_datetime_field()


class PasswordResetToken(BaseTable, table=True):
    """Single-use — `used_at` set on redemption; a second attempt with the
    same token is rejected (spec Edge Cases)."""

    __tablename__ = "password_reset_tokens"

    user_id: uuid.UUID = Field(foreign_key="users.id", nullable=False, index=True)
    token_hash: str = Field(sa_column_kwargs={"unique": True}, nullable=False)
    expires_at: datetime = tz_datetime_field(nullable=False)
    used_at: datetime | None = tz_datetime_field()
