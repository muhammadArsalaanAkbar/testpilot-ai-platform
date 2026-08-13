"""Reports & Analytics routes (contracts/reports-api.md, T185, T188)."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query

from testpilot.api.deps import CurrentUser, get_current_user
from testpilot.api.pagination import PaginationParams
from testpilot.core.exceptions import NotImplementedYetError
from testpilot.execution.models import TestRun
from testpilot.execution.schemas import TestRunPublic
from testpilot.reports import service
from testpilot.reports.schemas import (
    IssuesBySeverityResponse,
    ReportSummaryResponse,
    RunHistoryResponse,
)

router = APIRouter(prefix="/projects/{project_id}/reports", tags=["reports"])
org_router = APIRouter(prefix="/organizations/current/reports", tags=["reports"])


def _run_to_public(run: TestRun) -> TestRunPublic:
    return TestRunPublic(
        id=run.id,
        project_id=run.project_id,
        status=run.status,
        summary_total=run.summary_total,
        summary_passed=run.summary_passed,
        summary_failed=run.summary_failed,
        summary_skipped=run.summary_skipped,
        started_at=run.started_at,
        completed_at=run.completed_at,
        created_at=run.created_at,
    )


@router.get("/summary", response_model=ReportSummaryResponse)
async def get_summary(
    project_id: uuid.UUID,
    from_: date | None = Query(None, alias="from"),
    to: date | None = Query(None),
    current_user: CurrentUser = Depends(get_current_user),
) -> ReportSummaryResponse:
    summary = await service.get_summary(
        organization_id=uuid.UUID(current_user.organization_id), project_id=project_id, from_date=from_, to_date=to
    )
    return ReportSummaryResponse(
        total=summary.total,
        passed=summary.passed,
        failed=summary.failed,
        skipped=summary.skipped,
        pass_percentage=summary.pass_percentage,
        failure_percentage=summary.failure_percentage,
        coverage_percentage=summary.coverage_percentage,
    )


@router.get("/issues-by-severity", response_model=IssuesBySeverityResponse)
async def get_issues_by_severity(
    project_id: uuid.UUID,
    from_: date | None = Query(None, alias="from"),
    to: date | None = Query(None),
    current_user: CurrentUser = Depends(get_current_user),
) -> IssuesBySeverityResponse:
    counts = await service.get_issues_by_severity(
        organization_id=uuid.UUID(current_user.organization_id), project_id=project_id, from_date=from_, to_date=to
    )
    return IssuesBySeverityResponse(**{severity.value: count for severity, count in counts.items()})


@router.get("/run-history", response_model=RunHistoryResponse)
async def get_run_history(
    project_id: uuid.UUID,
    pagination: PaginationParams = Depends(),
    current_user: CurrentUser = Depends(get_current_user),
) -> RunHistoryResponse:
    runs = await service.list_run_history(
        organization_id=uuid.UUID(current_user.organization_id),
        project_id=project_id,
        page=pagination.page,
        page_size=pagination.page_size,
    )
    return RunHistoryResponse(items=[_run_to_public(r) for r in runs])


@router.get("/trend", status_code=501)
async def get_trend(project_id: uuid.UUID, current_user: CurrentUser = Depends(get_current_user)) -> None:
    """Future scope (FR-108) — pass-rate trend line over time."""
    raise NotImplementedYetError("Trend reporting is not available yet")


@org_router.get("/rollup", status_code=501)
async def get_organization_rollup(current_user: CurrentUser = Depends(get_current_user)) -> None:
    """Future scope (FR-111) — Organization-level rollup across all projects."""
    raise NotImplementedYetError("Organization-level rollup reporting is not available yet")
