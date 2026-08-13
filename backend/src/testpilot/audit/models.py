import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Column, Index, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from testpilot.core.models import IDMixin, tz_datetime_field


def _utcnow() -> datetime:
    return datetime.now(UTC)


class AuditLogEntry(IDMixin, SQLModel, table=True):
    """Append-only; no update/delete path is built for it at the
    application layer (SEC-010). Deliberately does NOT follow the standard
    tenant-table convention (data-model.md lists it as an explicit
    exception alongside users/organizations/subscription_plans):
    `organization_id` is nullable (some events, e.g. a failed login from an
    unauthenticated request, have no established Organization context) and
    there is no `updated_at` (a log entry is never modified after creation).
    """

    __tablename__ = "audit_log_entries"
    __table_args__ = (
        Index("ix_audit_log_entries_org_created_at", "organization_id", text("created_at DESC")),
        Index("ix_audit_log_entries_actor_created_at", "actor_user_id", text("created_at DESC")),
    )

    # Not index=True: these are covered by the composite
    # (column, created_at DESC) indexes above/data-model.md specifies,
    # not single-column indexes.
    organization_id: uuid.UUID | None = Field(default=None, foreign_key="organizations.id")
    actor_user_id: uuid.UUID | None = Field(default=None, foreign_key="users.id")
    action: str = Field(nullable=False)
    resource_type: str | None = None
    resource_id: uuid.UUID | None = None
    # "metadata" is a reserved attribute name on SQLAlchemy's declarative
    # base (Base.metadata), hence the Python-side "event_metadata" paired
    # with an explicit DB column name of "metadata" (matching data-model.md).
    event_metadata: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column("metadata", JSONB, nullable=False)
    )
    created_at: datetime = tz_datetime_field(nullable=False, default_factory=_utcnow)
