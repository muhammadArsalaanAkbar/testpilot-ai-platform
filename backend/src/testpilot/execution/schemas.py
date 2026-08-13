"""Request/response schemas for the Test Runs API (contracts/test-runs-api.md)."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from testpilot.execution.artifact_models import ArtifactType
from testpilot.execution.models import TestResultStatus, TestRunStatus


class CreateTestRunRequest(BaseModel):
    test_case_ids: list[uuid.UUID] = Field(min_length=1)


class TestRunPublic(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    status: TestRunStatus
    summary_total: int
    summary_passed: int
    summary_failed: int
    summary_skipped: int
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class TestResultSummaryPublic(BaseModel):
    id: uuid.UUID
    test_run_id: uuid.UUID
    test_case_id: uuid.UUID
    status: TestResultStatus
    failure_step_index: int | None
    error_message: str | None
    started_at: datetime
    completed_at: datetime
    duration_ms: int


class TestRunListResponse(BaseModel):
    items: list[TestRunPublic]
    page: int
    page_size: int
    total: int


class TestRunDetailResponse(BaseModel):
    test_run: TestRunPublic
    results: list[TestResultSummaryPublic]


class StepLogEntryPublic(BaseModel):
    step_index: int
    action_type: str
    status: str
    message: str | None
    timestamp: str


class ArtifactPublic(BaseModel):
    id: uuid.UUID
    type: ArtifactType
    # `_storage-note` (contracts/_conventions.md): a short-lived signed URL,
    # never a permanent public link. `None` if the underlying binary has
    # been purged (DATA-003) — the artifact's existence/metadata survives,
    # only the viewable content doesn't.
    url: str | None
    captured_at: datetime


class TestResultDetailResponse(BaseModel):
    test_result: TestResultSummaryPublic
    execution_log: list[StepLogEntryPublic]
    artifacts: list[ArtifactPublic]
    # Populated once AI failure analysis exists (Phase 13); an empty list is
    # the correct MVP-so-far value, not a placeholder — same pattern as
    # testcases/schemas.py's TestCaseDetailResponse.recent_results.
    ai_analyses: list[Any] = []
