"""Test-run creation/query/retry business logic (contracts/test-runs-api.md,
FR-069, FR-073, T138/T139).

The async-job shape mirrors ai_generation/service.py's split: `create_test_run`
here is the DB-side validate-and-reserve step (plan-limit check, FR-057's
rejected-case guard, `queued` row) called by the route (T140) before it
enqueues onto the Redis queue; the actual work (driving the browser through
every case) is `execution/runner.py`'s `run_test_run`, invoked only by the
worker job handler (T141) — never inline in an API request (NFR-004/NFR-006).
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from testpilot.billing import service as billing_service
from testpilot.core.db import session_scope
from testpilot.core.exceptions import (
    ConflictError,
    NotFoundError,
    ProjectArchivedError,
    ValidationFailedError,
)
from testpilot.execution.artifact_models import Artifact
from testpilot.execution.models import (
    TestResult,
    TestResultStatus,
    TestRun,
    TestRunCase,
    TestRunStatus,
)
from testpilot.projects.models import Project, ProjectStatus
from testpilot.storage.base import ArtifactStorage
from testpilot.testcases.models import TestCase, TestCaseStatus

# Short-lived per SEC-013 ("prevent serving as executable content" / no
# durable public link) — long enough for a page load plus lightbox viewing,
# short enough that a leaked link is worthless shortly after.
ARTIFACT_URL_EXPIRES_IN_SECONDS = 300


class NoApprovedCasesSelectedError(ValidationFailedError):
    """FR-057: a rejected-status case can never be selected into a new run."""

    code = "no_approved_cases_selected"


class RunNotCompletedError(ConflictError):
    """FR-073: retry-failed only applies to a run that has reached a terminal state."""

    code = "run_not_completed"


async def _get_project_or_404(session: AsyncSession, *, organization_id: uuid.UUID, project_id: uuid.UUID) -> Project:
    result = await session.execute(
        select(Project).where(Project.id == project_id, Project.organization_id == organization_id)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise NotFoundError("Project not found")
    return project


async def _get_test_run_or_404(
    session: AsyncSession, *, organization_id: uuid.UUID, project_id: uuid.UUID, test_run_id: uuid.UUID
) -> TestRun:
    result = await session.execute(
        select(TestRun).where(
            TestRun.id == test_run_id, TestRun.project_id == project_id, TestRun.organization_id == organization_id
        )
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise NotFoundError("Test run not found")
    return run


async def create_test_run(
    *,
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
    initiated_by_user_id: uuid.UUID,
    test_case_ids: list[uuid.UUID],
) -> TestRun:
    async with session_scope(organization_id=str(organization_id)) as session:
        project = await _get_project_or_404(session, organization_id=organization_id, project_id=project_id)
        if project.status == ProjectStatus.archived:
            raise ProjectArchivedError("Cannot start a test run for an archived project")

        cases_result = await session.execute(
            select(TestCase).where(
                TestCase.id.in_(test_case_ids),
                TestCase.project_id == project_id,
                TestCase.organization_id == organization_id,
            )
        )
        cases_by_id = {case.id: case for case in cases_result.scalars().all()}
        missing = [str(case_id) for case_id in test_case_ids if case_id not in cases_by_id]
        if missing:
            raise NotFoundError("One or more test cases were not found", details={"missing_test_case_ids": missing})

        rejected = [str(case_id) for case_id, case in cases_by_id.items() if case.status == TestCaseStatus.rejected]
        if rejected:
            raise NoApprovedCasesSelectedError(
                "Cannot start a test run: one or more selected test cases are rejected",
                details={"rejected_test_case_ids": rejected},
            )

    # FR-123: plan-limit check outside the row-creating transaction (same
    # ordering as ai_generation's start_generation_run) — a rejected
    # reservation never leaves an orphaned queued row behind.
    if test_case_ids:
        await billing_service.check_and_reserve_period_usage(
            organization_id=organization_id, metric="test_executions", amount=len(test_case_ids)
        )

    async with session_scope(organization_id=str(organization_id)) as session:
        run = TestRun(
            organization_id=organization_id,
            project_id=project_id,
            initiated_by_user_id=initiated_by_user_id,
            status=TestRunStatus.queued,
            summary_total=len(test_case_ids),
        )
        session.add(run)
        await session.flush()

        run_cases = [
            TestRunCase(
                organization_id=organization_id, test_run_id=run.id, test_case_id=case_id, order_index=index
            )
            for index, case_id in enumerate(test_case_ids)
        ]
        session.add_all(run_cases)

        await session.flush()
        await session.refresh(run)
        return run


async def get_test_run(
    *, organization_id: uuid.UUID, project_id: uuid.UUID, test_run_id: uuid.UUID
) -> tuple[TestRun, list[TestResult]]:
    async with session_scope(organization_id=str(organization_id)) as session:
        run = await _get_test_run_or_404(
            session, organization_id=organization_id, project_id=project_id, test_run_id=test_run_id
        )
        results_result = await session.execute(
            select(TestResult).where(TestResult.test_run_id == test_run_id).order_by(TestResult.started_at)
        )
        return run, list(results_result.scalars().all())


async def list_test_runs(
    *, organization_id: uuid.UUID, project_id: uuid.UUID, page: int = 1, page_size: int = 25
) -> tuple[list[TestRun], int]:
    async with session_scope(organization_id=str(organization_id)) as session:
        await _get_project_or_404(session, organization_id=organization_id, project_id=project_id)

        total_result = await session.execute(
            select(func.count()).select_from(TestRun).where(
                TestRun.project_id == project_id, TestRun.organization_id == organization_id
            )
        )
        total = total_result.scalar_one()

        result = await session.execute(
            select(TestRun)
            .where(TestRun.project_id == project_id, TestRun.organization_id == organization_id)
            .order_by(TestRun.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), total


async def retry_failed(
    *, organization_id: uuid.UUID, project_id: uuid.UUID, test_run_id: uuid.UUID, initiated_by_user_id: uuid.UUID
) -> TestRun:
    async with session_scope(organization_id=str(organization_id)) as session:
        previous = await _get_test_run_or_404(
            session, organization_id=organization_id, project_id=project_id, test_run_id=test_run_id
        )
        if previous.status not in (TestRunStatus.completed, TestRunStatus.error):
            raise RunNotCompletedError("Cannot retry a test run that has not reached a terminal state")

        # FR-073: only cases that did not pass. "failed" and "error" both
        # count as "not passed" here — an engine-level crash isn't a result
        # a user would consider done either. "skipped" is excluded: it means
        # the case had nothing to execute, and retrying would just skip
        # again.
        failed_result = await session.execute(
            select(TestResult.test_case_id).where(
                TestResult.test_run_id == test_run_id,
                TestResult.status.in_([TestResultStatus.failed, TestResultStatus.error]),
            )
        )
        failed_case_ids = list(failed_result.scalars().all())

    return await create_test_run(
        organization_id=organization_id,
        project_id=project_id,
        initiated_by_user_id=initiated_by_user_id,
        test_case_ids=failed_case_ids,
    )


async def get_test_result(
    *,
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
    test_run_id: uuid.UUID,
    test_result_id: uuid.UUID,
    storage: ArtifactStorage,
) -> tuple[TestResult, list[tuple[Artifact, str | None]]]:
    """Result detail (T152, contracts/test-runs-api.md, FR-072): the result
    row plus its artifacts paired with a freshly-minted signed URL for each
    (`None` if the artifact's binary has since been purged, DATA-003 — the
    row and the result's own outcome survive purge, only the URL doesn't).
    """
    async with session_scope(organization_id=str(organization_id)) as session:
        # Confirms the run belongs to this project/org before trusting the
        # result_id/run_id pairing below (also gives a clean 404 if the run
        # itself doesn't exist).
        run = await session.execute(
            select(TestRun).where(
                TestRun.id == test_run_id, TestRun.project_id == project_id, TestRun.organization_id == organization_id
            )
        )
        if run.scalar_one_or_none() is None:
            raise NotFoundError("Test run not found")

        result = await session.execute(
            select(TestResult).where(
                TestResult.id == test_result_id,
                TestResult.test_run_id == test_run_id,
                TestResult.organization_id == organization_id,
            )
        )
        test_result = result.scalar_one_or_none()
        if test_result is None:
            raise NotFoundError("Test result not found")

        artifacts_result = await session.execute(
            select(Artifact).where(Artifact.test_result_id == test_result_id).order_by(Artifact.captured_at)
        )
        artifacts = list(artifacts_result.scalars().all())

    artifacts_with_urls: list[tuple[Artifact, str | None]] = []
    for artifact in artifacts:
        url: str | None = None
        if artifact.storage_key is not None:
            try:
                url = await storage.get_url(artifact.storage_key, expires_in=ARTIFACT_URL_EXPIRES_IN_SECONDS)
            except Exception:  # noqa: BLE001 — a storage hiccup here must not 500 the whole result view
                url = None
        artifacts_with_urls.append((artifact, url))

    return test_result, artifacts_with_urls
