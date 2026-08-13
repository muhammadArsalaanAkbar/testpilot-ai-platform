"""Request/response schemas for the Notifications API (contracts/notifications-api.md)."""

import uuid
from datetime import datetime

from pydantic import BaseModel

from testpilot.notifications.models import NotificationType


class NotificationPublic(BaseModel):
    id: uuid.UUID
    type: NotificationType
    related_entity_type: str
    related_entity_id: uuid.UUID
    # Additive beyond the contract's documented row shape — see
    # notifications/service.py's NotificationContext docstring for why the
    # frontend needs these to build a deep link.
    project_id: uuid.UUID | None
    test_run_id: uuid.UUID | None
    read_at: datetime | None
    created_at: datetime


class NotificationListResponse(BaseModel):
    items: list[NotificationPublic]
    unread_count: int


class MarkReadResponse(BaseModel):
    notification: NotificationPublic
