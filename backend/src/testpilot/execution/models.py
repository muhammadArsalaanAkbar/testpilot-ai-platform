"""Execution persistence models (data-model.md `test_runs`/`test_run_cases`/
`test_results`, T136).

Deliberately compose `IDMixin` + `OrgScopedMixin` directly (not `TenantTable`)
for the same reason `ai_generation/models.py`'s `GenerationRun` does:
data-model.md's exact column lists for these three tables have no generic
`updated_at` — status transitions are the row's own history (`started_at`/
`completed_at`), not a separately-tracked "last modified" concept.

`artifacts` (data-model.md) is intentionally NOT modeled here — its DB table
plus the object-storage adapter is tasks.md's Phase 12 (T148-T151), which
depends on this phase's runner (T137) already existing. Phase 11's runner
receives `CapturedArtifact` objects from `BrowserAutomationEngine.run_test_case`
(Phase 10) but has nowhere durable to persist them yet; that wiring is
Phase 12's job, not a gap in this phase.
"""

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import Column, ForeignKey, Index, UniqueConstraint
from sqlalchemy import Uuid as SAUuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from testpilot.core.models import IDMixin, OrgScopedMixin, tz_datetime_field


def _utcnow() -> datetime:
    return datetime.now(UTC)


class TestRunStatus(StrEnum):
    queued = "queued"
    running = "running"
    completed = "completed"
    error = "error"


class TestResultStatus(StrEnum):
    passed = "passed"
    failed = "failed"
    skipped = "skipped"
    error = "error"


class TestRun(IDMixin, OrgScopedMixin, SQLModel, table=True):
    """One execution of one or more test cases against a project's
    configured URL (data-model.md `test_runs`, FR-069-FR-076)."""

    __tablename__ = "test_runs"
    __table_args__ = (
        Index("ix_test_runs_project_id_created_at", "project_id", "created_at"),
        Index("ix_test_runs_organization_id_status", "organization_id", "status"),
    )

    project_id: uuid.UUID = Field(
        sa_column=Column(SAUuid, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    initiated_by_user_id: uuid.UUID = Field(foreign_key="users.id", nullable=False)
    status: TestRunStatus = Field(default=TestRunStatus.queued, nullable=False)
    summary_total: int = Field(default=0, nullable=False)
    summary_passed: int = Field(default=0, nullable=False)
    summary_failed: int = Field(default=0, nullable=False)
    summary_skipped: int = Field(default=0, nullable=False)
    started_at: datetime | None = tz_datetime_field(nullable=True)
    completed_at: datetime | None = tz_datetime_field(nullable=True)
    created_at: datetime = tz_datetime_field(nullable=False, default_factory=_utcnow)


class TestRunCase(IDMixin, OrgScopedMixin, SQLModel, table=True):
    """Join table recording which test_cases were selected into a test_run
    (data-model.md `test_run_cases`) — exists independent of whether a
    result exists yet, and is what "retry failed" (FR-073) scopes a
    follow-up run to."""

    __tablename__ = "test_run_cases"
    __table_args__ = (UniqueConstraint("test_run_id", "test_case_id", name="uq_test_run_cases_run_case"),)

    test_run_id: uuid.UUID = Field(
        sa_column=Column(SAUuid, ForeignKey("test_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    test_case_id: uuid.UUID = Field(
        sa_column=Column(SAUuid, ForeignKey("test_cases.id", ondelete="CASCADE"), nullable=False)
    )
    order_index: int = Field(nullable=False)


class TestResult(IDMixin, OrgScopedMixin, SQLModel, table=True):
    """The outcome of executing one test case within one test_run
    (data-model.md `test_results`, FR-070/FR-074/FR-075)."""

    __tablename__ = "test_results"
    __table_args__ = (
        Index("ix_test_results_test_run_id", "test_run_id"),
        Index("ix_test_results_test_case_id_created", "test_case_id", "started_at"),
        Index("ix_test_results_organization_id_status", "organization_id", "status"),
    )

    test_run_id: uuid.UUID = Field(
        sa_column=Column(SAUuid, ForeignKey("test_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    test_case_id: uuid.UUID = Field(
        sa_column=Column(SAUuid, ForeignKey("test_cases.id", ondelete="CASCADE"), nullable=False)
    )
    status: TestResultStatus = Field(nullable=False)
    execution_log: list[dict[str, Any]] = Field(
        default_factory=list, sa_column=Column(JSONB, nullable=False, server_default="[]")
    )
    failure_step_index: int | None = None
    error_message: str | None = None
    started_at: datetime = tz_datetime_field(nullable=False, default_factory=_utcnow)
    completed_at: datetime = tz_datetime_field(nullable=False, default_factory=_utcnow)
    duration_ms: int = Field(nullable=False)
