"""Reports & Analytics business logic (contracts/reports-api.md, FR-104-FR-111, T184).

Computed on read from `test_runs`/`test_results`/`issues`, never a
separately maintained table at MVP (plan.md's Reports & Analytics
Architecture) — every aggregation here is scoped to `organization_id` +
`project_id` + the requested date range so results never leak across
tenants (FR-110), matching the RLS policy that also guards these tables.

FR-109 note: every value below is a flat, already-computed scalar/count —
adding a PDF/CSV export later is a pure presentation layer over this same
service's return values, requiring no redesign of this aggregation.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from testpilot.core.db import session_scope
from testpilot.core.exceptions import NotFoundError
from testpilot.execution.models import TestResult, TestRun
from testpilot.issues.models import Issue, IssueSeverity
from testpilot.projects.models import Project
from testpilot.testcases.models import TestCase, TestCaseStatus

DEFAULT_RANGE_DAYS = 30


def _utcnow() -> datetime:
    return datetime.now(UTC)


def resolve_range(from_date: date | None, to_date: date | None) -> tuple[datetime, datetime]:
    """ISO dates (contract: `?from=&to=`) widened to inclusive UTC
    day-boundary datetimes for filtering timestamptz columns."""
    end_date = to_date or _utcnow().date()
    start_date = from_date or (end_date - timedelta(days=DEFAULT_RANGE_DAYS))
    start = datetime.combine(start_date, time.min, tzinfo=UTC)
    end = datetime.combine(end_date, time.max, tzinfo=UTC)
    return start, end


async def _get_project_or_404(session: AsyncSession, *, organization_id: uuid.UUID, project_id: uuid.UUID) -> Project:
    result = await session.execute(
        select(Project).where(Project.id == project_id, Project.organization_id == organization_id)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise NotFoundError("Project not found")
    return project


@dataclass(frozen=True)
class ReportSummary:
    total: int
    passed: int
    failed: int
    skipped: int
    pass_percentage: float
    failure_percentage: float
    coverage_percentage: float


async def get_summary(
    *, organization_id: uuid.UUID, project_id: uuid.UUID, from_date: date | None, to_date: date | None
) -> ReportSummary:
    start, end = resolve_range(from_date, to_date)

    async with session_scope(organization_id=str(organization_id)) as session:
        await _get_project_or_404(session, organization_id=organization_id, project_id=project_id)

        # Sums the denormalized test_runs.summary_* counters (plan.md:
        # "using test_runs.summary_* counters to avoid re-scanning every
        # test_result row for totals") rather than counting test_results.
        totals_result = await session.execute(
            select(
                func.coalesce(func.sum(TestRun.summary_total), 0),
                func.coalesce(func.sum(TestRun.summary_passed), 0),
                func.coalesce(func.sum(TestRun.summary_failed), 0),
                func.coalesce(func.sum(TestRun.summary_skipped), 0),
            ).where(
                TestRun.organization_id == organization_id,
                TestRun.project_id == project_id,
                TestRun.created_at >= start,
                TestRun.created_at <= end,
            )
        )
        total, passed, failed, skipped = totals_result.one()

        approved_count_result = await session.execute(
            select(func.count())
            .select_from(TestCase)
            .where(
                TestCase.organization_id == organization_id,
                TestCase.project_id == project_id,
                TestCase.status == TestCaseStatus.approved,
            )
        )
        approved_count = approved_count_result.scalar_one()

        # FR-105: approved cases with >=1 result *within the range* — a
        # case's own most-recent-result timestamp, not the parent run's,
        # since a long-lived run's cases could otherwise be counted as
        # "covered" outside the window they actually executed in.
        covered_count_result = await session.execute(
            select(func.count(func.distinct(TestResult.test_case_id)))
            .select_from(TestResult)
            .join(TestCase, TestCase.id == TestResult.test_case_id)
            .where(
                TestResult.organization_id == organization_id,
                TestCase.project_id == project_id,
                TestCase.status == TestCaseStatus.approved,
                TestResult.completed_at >= start,
                TestResult.completed_at <= end,
            )
        )
        covered_count = covered_count_result.scalar_one()

    pass_percentage = (passed / total * 100) if total else 0.0
    failure_percentage = (failed / total * 100) if total else 0.0
    coverage_percentage = (covered_count / approved_count * 100) if approved_count else 0.0

    return ReportSummary(
        total=total,
        passed=passed,
        failed=failed,
        skipped=skipped,
        pass_percentage=pass_percentage,
        failure_percentage=failure_percentage,
        coverage_percentage=coverage_percentage,
    )


async def get_issues_by_severity(
    *, organization_id: uuid.UUID, project_id: uuid.UUID, from_date: date | None, to_date: date | None
) -> dict[IssueSeverity, int]:
    start, end = resolve_range(from_date, to_date)

    async with session_scope(organization_id=str(organization_id)) as session:
        await _get_project_or_404(session, organization_id=organization_id, project_id=project_id)

        result = await session.execute(
            select(Issue.severity, func.count())
            .select_from(Issue)
            .where(
                Issue.organization_id == organization_id,
                Issue.project_id == project_id,
                Issue.created_at >= start,
                Issue.created_at <= end,
            )
            .group_by(Issue.severity)
        )
        counts: dict[IssueSeverity, int] = dict(result.all())

    return {severity: counts.get(severity, 0) for severity in IssueSeverity}


async def list_run_history(
    *, organization_id: uuid.UUID, project_id: uuid.UUID, page: int = 1, page_size: int = 25
) -> list[TestRun]:
    async with session_scope(organization_id=str(organization_id)) as session:
        await _get_project_or_404(session, organization_id=organization_id, project_id=project_id)

        result = await session.execute(
            select(TestRun)
            .where(TestRun.organization_id == organization_id, TestRun.project_id == project_id)
            .order_by(TestRun.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all())
