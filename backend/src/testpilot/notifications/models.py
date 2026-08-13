"""`notifications` model (data-model.md `notifications`, T190, FR-112-FR-116)."""

import uuid
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import Index
from sqlmodel import Field, SQLModel

from testpilot.core.models import IDMixin, OrgScopedMixin, tz_datetime_field


def _utcnow() -> datetime:
    return datetime.now(UTC)


class NotificationType(StrEnum):
    run_completed = "run_completed"
    run_failed_critical = "run_failed_critical"
    ai_analysis_completed = "ai_analysis_completed"
    ai_analysis_failed = "ai_analysis_failed"


class Notification(IDMixin, OrgScopedMixin, SQLModel, table=True):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_user_id_read_at", "user_id", "read_at"),
        Index("ix_notifications_user_id_created_at", "user_id", "created_at"),
    )

    user_id: uuid.UUID = Field(foreign_key="users.id", nullable=False, index=True)
    type: NotificationType = Field(nullable=False)
    # Free-text on purpose (data-model.md): "test_run"/"test_result" today,
    # extensible to other entity kinds (e.g. "issue") later without a schema
    # change.
    related_entity_type: str = Field(nullable=False)
    related_entity_id: uuid.UUID = Field(nullable=False)
    read_at: datetime | None = tz_datetime_field(nullable=True)
    created_at: datetime = tz_datetime_field(nullable=False, default_factory=_utcnow)
