import uuid
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import Column, ForeignKey, Index
from sqlalchemy import Uuid as SAUuid
from sqlalchemy.dialects.postgresql import ARRAY
from sqlmodel import Field, SQLModel

from testpilot.core.models import IDMixin, OrgScopedMixin, tz_datetime_field


def _utcnow() -> datetime:
    return datetime.now(UTC)


class GenerationScope(StrEnum):
    full_batch = "full_batch"
    single_case = "single_case"


class GenerationStatus(StrEnum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class GenerationRun(IDMixin, OrgScopedMixin, SQLModel, table=True):
    """Tracks one AI test-case generation job's lifecycle (data-model.md
    `generation_runs`, FR-047's concurrency guard, and the frontend's
    single-resource polling target). Deliberately does NOT use `TenantTable`
    (unlike most tenant tables): data-model.md specifies `created_at` /
    `completed_at` only, no generic `updated_at` — status transitions are
    the row's own history, not a separately-tracked "last modified" concept
    (same reasoning `audit_log_entries` documents for its own deviation).
    """

    __tablename__ = "generation_runs"
    __table_args__ = (Index("ix_generation_runs_project_id_status", "project_id", "status"),)

    project_id: uuid.UUID = Field(
        sa_column=Column(SAUuid, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    requested_by_user_id: uuid.UUID = Field(foreign_key="users.id", nullable=False)
    scope: GenerationScope = Field(nullable=False)
    target_test_case_id: uuid.UUID | None = Field(
        default=None,
        sa_column=Column(SAUuid, ForeignKey("test_cases.id", ondelete="CASCADE"), nullable=True),
    )
    status: GenerationStatus = Field(default=GenerationStatus.queued, nullable=False)
    failure_reason: str | None = None
    # Not in data-model.md's column list — added because the polling
    # contract (contracts/test-cases-api.md) requires the completed run to
    # report which draft test cases it created, and test_cases has no FK
    # back to generation_runs; this is the minimal-footprint way to satisfy
    # that without touching the already-in-use test_cases table.
    created_test_case_ids: list[uuid.UUID] = Field(
        default_factory=list, sa_column=Column(ARRAY(SAUuid), nullable=False, server_default="{}")
    )
    created_at: datetime = tz_datetime_field(nullable=False, default_factory=_utcnow)
    completed_at: datetime | None = tz_datetime_field(nullable=True)
