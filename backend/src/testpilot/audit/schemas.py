"""Response schemas for the audit-log viewing endpoint (T209, FR-129)."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AuditLogEntryPublic(BaseModel):
    id: uuid.UUID
    action: str
    actor_user_id: uuid.UUID | None
    resource_type: str | None
    resource_id: uuid.UUID | None
    event_metadata: dict[str, Any]
    created_at: datetime


class AuditLogListResponse(BaseModel):
    items: list[AuditLogEntryPublic]
    page: int
    page_size: int
    total: int
