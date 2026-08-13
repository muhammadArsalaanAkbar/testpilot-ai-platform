"""Request/response schemas for the Reports API (contracts/reports-api.md)."""

from pydantic import BaseModel

from testpilot.execution.schemas import TestRunPublic


class ReportSummaryResponse(BaseModel):
    total: int
    passed: int
    failed: int
    skipped: int
    pass_percentage: float
    failure_percentage: float
    coverage_percentage: float


class IssuesBySeverityResponse(BaseModel):
    minor: int
    major: int
    critical: int
    blocker: int


class RunHistoryResponse(BaseModel):
    items: list[TestRunPublic]
