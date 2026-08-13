"""Response schema for the AI-analysis endpoints on the test-runs router
(contracts/test-runs-api.md)."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from testpilot.ai_analysis.models import AnalysisSeverity


class AIAnalysisPublic(BaseModel):
    id: uuid.UUID
    test_result_id: uuid.UUID
    # "queued" only ever appears in the synthetic response the POST .../analyze
    # endpoint returns immediately — no persisted row has this status (see
    # ai_analysis/models.py's module docstring).
    status: Literal["queued", "completed", "failed"]
    explanation: str | None
    root_cause: str | None
    severity: AnalysisSeverity | None
    suggested_fix: str | None
    # FR-082: always populated, independent of AI provider success — derived
    # straight from the persisted TestResult/TestStep, not an AI-generated
    # field (see ai_analysis/service.py's get_expected_vs_actual).
    expected_vs_actual: str
    failure_reason: str | None
    provider: str | None
    model: str | None
    created_at: datetime | None
