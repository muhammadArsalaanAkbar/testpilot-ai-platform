"""`issues`/`issue_attachments` models (data-model.md, T169, FR-087-FR-096).

`Issue` uses `TenantTable` directly (unlike `TestRun`/`TestResult`/`AIAnalysis`)
because data-model.md's `issues` table explicitly lists both `created_at`
*and* `updated_at` — an issue's own status/fields genuinely get edited after
creation (PATCH, T171), unlike those append-only execution-history rows.
"""

import uuid
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import Column, ForeignKey, Index
from sqlalchemy import Uuid as SAUuid
from sqlmodel import Field, SQLModel

from testpilot.core.models import IDMixin, OrgScopedMixin, TenantTable, tz_datetime_field


def _utcnow() -> datetime:
    return datetime.now(UTC)


class IssueSeverity(StrEnum):
    """Same value set as testcases.models.TestCaseSeverity — kept separate
    since an issue's severity is independently editable after creation, not
    derived from its source test case (same reasoning ai_analysis.models.
    AnalysisSeverity documents for its own, otherwise-identical, enum)."""

    minor = "minor"
    major = "major"
    critical = "critical"
    blocker = "blocker"


class IssuePriority(StrEnum):
    """Same value set as testcases.models.TestCasePriority, kept separate
    for the same reason as IssueSeverity above."""

    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class IssueStatus(StrEnum):
    """Declared open-to-wont_fix in the lifecycle order contracts/issues-api.md
    describes (open -> in_progress -> resolved -> closed, or open/in_progress
    -> wont_fix) — see issues/service.py's transition-validation for the
    actual state-machine rules this ordering alone doesn't encode."""

    open = "open"
    in_progress = "in_progress"
    resolved = "resolved"
    closed = "closed"
    wont_fix = "wont_fix"


class IssueAttachmentType(StrEnum):
    screenshot = "screenshot"
    log = "log"


class Issue(TenantTable, table=True):
    """A tracked bug/finding (data-model.md `issues`, FR-087-FR-096)."""

    __tablename__ = "issues"
    __table_args__ = (
        Index("ix_issues_project_id_status", "project_id", "status"),
        Index("ix_issues_organization_id_severity", "organization_id", "severity"),
    )

    project_id: uuid.UUID = Field(
        sa_column=Column(SAUuid, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    title: str = Field(nullable=False)
    description: str = Field(nullable=False)
    severity: IssueSeverity = Field(nullable=False)
    priority: IssuePriority = Field(nullable=False)
    status: IssueStatus = Field(default=IssueStatus.open, nullable=False)
    # Future (FR-094): populated once multi-member Organizations exist.
    assignee_user_id: uuid.UUID | None = Field(default=None, foreign_key="users.id", nullable=True)
    # SET NULL, not CASCADE: hard-deleting the source test case/run must not
    # delete the issue it produced (data-model.md's own note) — FR-096's
    # "preserve the link ... even if ... superseded" is satisfied trivially
    # by ordinary edits (same row id, FK untouched); this ondelete handles
    # only the harder case of the source row being hard-deleted outright.
    source_test_case_id: uuid.UUID | None = Field(
        default=None, sa_column=Column(SAUuid, ForeignKey("test_cases.id", ondelete="SET NULL"), nullable=True)
    )
    source_test_run_id: uuid.UUID | None = Field(
        default=None, sa_column=Column(SAUuid, ForeignKey("test_runs.id", ondelete="SET NULL"), nullable=True)
    )
    created_by_user_id: uuid.UUID = Field(foreign_key="users.id", nullable=False)


class IssueAttachment(IDMixin, OrgScopedMixin, SQLModel, table=True):
    """A screenshot/log attached to an issue (data-model.md `issue_attachments`,
    FR-087/FR-092) — metadata/reference only, same DATA-002 pattern as
    `execution.artifact_models.Artifact`; `storage_key` is NOT NULL here
    (unlike that table) since issue_attachments has no documented retention
    purge (DATA-003 only calls out *test execution* artifacts)."""

    __tablename__ = "issue_attachments"
    __table_args__ = (Index("ix_issue_attachments_issue_id", "issue_id"),)

    issue_id: uuid.UUID = Field(
        sa_column=Column(SAUuid, ForeignKey("issues.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    type: IssueAttachmentType = Field(nullable=False)
    storage_key: str = Field(nullable=False)
    created_at: datetime = tz_datetime_field(nullable=False, default_factory=_utcnow)
