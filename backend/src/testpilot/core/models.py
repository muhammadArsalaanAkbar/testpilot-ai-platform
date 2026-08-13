import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(UTC)


def tz_datetime_field(
    *, nullable: bool = True, default_factory: Callable[[], datetime] | None = None
) -> Any:
    """A `datetime` Field backed by a real Postgres `timestamptz` column
    (data-model.md's shared-column convention) — SQLModel's default
    `datetime` mapping produces a timezone-naive column otherwise, which
    would silently disagree with the timezone-aware Python values this
    codebase produces (see `_utcnow`). Every timestamp column in this
    project — created_at/updated_at here and every nullable timestamp field
    in domain models (e.g. auth/models.py's expires_at/revoked_at) — should
    go through this helper rather than declaring `datetime` directly.

    Centralized here (rather than inlined at each call site) for two
    reasons: (1) `sa_type=` must be used instead of `sa_column=Column(...)`,
    since a `Column` instance can only belong to one Table — constructing it
    once and reusing it across every subclass that inherits a mixin (or
    calls this helper) fails with "Column already assigned to Table" the
    moment a second table does so; `sa_type` shares only the stateless type
    object and lets SQLModel build a fresh Column per call. (2) SQLModel's
    `Field(sa_type=...)` stub is typed as `type[Any]`, but the runtime
    implementation passes it straight through as `Column(sa_type, ...)`,
    which also accepts an instance (`DateTime(timezone=True)`) — the `Any`
    return type here contains that one, single, justified suppression
    instead of repeating `# type: ignore[call-overload]` at every field.
    """
    if default_factory is not None:
        return Field(  # type: ignore[call-overload]  # see docstring: sa_type also accepts an instance at runtime
            default_factory=default_factory, sa_type=DateTime(timezone=True), nullable=nullable
        )
    return Field(  # type: ignore[call-overload]  # see docstring: sa_type also accepts an instance at runtime
        default=None, sa_type=DateTime(timezone=True), nullable=nullable
    )


class IDMixin(SQLModel):
    """Primary key convention shared by every table: a server-generatable UUID."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)


class TimestampMixin(SQLModel):
    """created_at/updated_at convention shared by every table."""

    created_at: datetime = tz_datetime_field(nullable=False, default_factory=_utcnow)
    updated_at: datetime = tz_datetime_field(nullable=False, default_factory=_utcnow)


class OrgScopedMixin(SQLModel):
    """organization_id convention shared by every tenant-owned table.

    Every table that includes this mixin MUST also have a matching Postgres
    Row-Level Security policy (see alembic/versions rls migrations) — the
    column alone is necessary but not sufficient for tenant isolation.
    """

    organization_id: uuid.UUID = Field(foreign_key="organizations.id", nullable=False, index=True)


class TenantTable(IDMixin, TimestampMixin, OrgScopedMixin):
    """Base class for tables scoped to a single Organization.

    Not every table uses this (users, refresh_tokens, password_reset_tokens,
    organizations itself, and subscription_plans are intentionally not
    Organization-scoped — see data-model.md for the rationale on each).
    """


class BaseTable(IDMixin, TimestampMixin):
    """Base class for tables that are not Organization-scoped."""
