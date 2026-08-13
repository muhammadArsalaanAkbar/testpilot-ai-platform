"""`ai_analyses` model (data-model.md `ai_analyses`, T158, FR-084).

Deliberately only two terminal statuses (`completed`/`failed`) — unlike
`generation_runs`/`test_runs`, a row here is created by the worker job
handler only once the analysis concludes, never upfront as `queued`
(worker/jobs/analyze_failure.py). The POST .../analyze endpoint (T161)
still satisfies contracts/test-runs-api.md's "202 {ai_analysis}
(status=queued -> poll same resource)" contract: it pre-generates the
row's eventual id and returns a synthetic, non-persisted `queued`
representation with that id; polling `GET .../analyses/{id}` 404s until
the worker creates the real row — the same id, so "poll the same
resource" holds, without deviating from data-model.md's exact enum.
"""

import uuid
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import Column, ForeignKey, Index
from sqlalchemy import Uuid as SAUuid
from sqlmodel import Field, SQLModel

from testpilot.core.models import IDMixin, OrgScopedMixin, tz_datetime_field


def _utcnow() -> datetime:
    return datetime.now(UTC)


class AIAnalysisStatus(StrEnum):
    completed = "completed"
    failed = "failed"


class AnalysisSeverity(StrEnum):
    """Same value set as testcases.models.TestCaseSeverity — kept as its own
    enum rather than importing that one, since this is a conceptually
    separate rating (the AI's assessment of a failure) from a test case's
    own defined severity, the same way TestResultStatus is kept separate
    from TestCaseStatus despite related meanings."""

    minor = "minor"
    major = "major"
    critical = "critical"
    blocker = "blocker"


class AIAnalysis(IDMixin, OrgScopedMixin, SQLModel, table=True):
    """AI failure analysis for one test result (data-model.md `ai_analyses`,
    FR-079-FR-086). Multiple rows per test_result_id are expected — FR-085's
    re-request creates a new row rather than updating the prior one; the
    most recent row (by created_at) is "current" for display purposes."""

    __tablename__ = "ai_analyses"
    __table_args__ = (Index("ix_ai_analyses_test_result_id_created_at", "test_result_id", "created_at"),)

    test_result_id: uuid.UUID = Field(
        sa_column=Column(SAUuid, ForeignKey("test_results.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    status: AIAnalysisStatus = Field(nullable=False)
    explanation: str | None = None
    root_cause: str | None = None
    severity: AnalysisSeverity | None = None
    suggested_fix: str | None = None
    failure_reason: str | None = None
    provider: str = Field(nullable=False)
    model: str = Field(nullable=False)
    created_at: datetime = tz_datetime_field(nullable=False, default_factory=_utcnow)
