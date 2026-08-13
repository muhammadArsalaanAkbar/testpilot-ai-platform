"""Execution orchestrator (contracts/worker-jobs.md `ExecuteTestRunJob`,
T137/T129-T131 continuation): sequences a test run's cases through
`BrowserAutomationEngine.run_test_case` (Phase 10, reused as-is — this module
never touches Playwright directly), persists a `test_results` row per case,
updates `test_cases.last_result` and the run's denormalized summary
counters. Invoked only from worker processes (worker/jobs/execute_test_run.py),
never inline in an API request (NFR-004/NFR-006).

Artifact persistence (T151): each `CapturedArtifact` (screenshots) `run_test_case`
returns is uploaded to object storage immediately after that case's result is
persisted — not batched at run-end, so a crash after a partial run doesn't
lose already-captured evidence (plan.md Execution Engine Architecture). A
`storage` upload failure is caught per-artifact and skipped rather than
failing the case: the TestResult's pass/fail outcome is already durable by
the time artifacts are attempted, satisfying spec Edge Cases' "the test
result must still be recorded ... rather than the whole test run failing."
"""

from __future__ import annotations

import contextlib
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select

from testpilot.core.db import session_scope
from testpilot.execution.artifact_models import Artifact, ArtifactType
from testpilot.execution.engine import BrowserAutomationEngine, CapturedArtifact
from testpilot.execution.models import (
    TestResult,
    TestResultStatus,
    TestRun,
    TestRunCase,
    TestRunStatus,
)
from testpilot.notifications import service as notifications_service
from testpilot.notifications.models import NotificationType
from testpilot.projects.models import Project
from testpilot.storage import get_storage
from testpilot.storage.base import ArtifactStorage
from testpilot.testcases.models import TestCase, TestCaseResult, TestCaseSeverity, TestStep

# TestCaseResult (FR-056) has no distinct "error" bucket — an engine-level
# crash is folded into "failed" for the case's last-known-result display,
# same as it's folded into summary_failed below (data-model.md's test_runs
# table has no summary_errored column either).
_RESULT_TO_LAST_RESULT: dict[TestResultStatus, TestCaseResult] = {
    TestResultStatus.passed: TestCaseResult.passed,
    TestResultStatus.failed: TestCaseResult.failed,
    TestResultStatus.skipped: TestCaseResult.skipped,
    TestResultStatus.error: TestCaseResult.failed,
}


async def run_test_run(
    *,
    test_run_id: uuid.UUID,
    organization_id: uuid.UUID,
    engine: BrowserAutomationEngine,
    storage: ArtifactStorage | None = None,
) -> None:
    """Handler-contract implementation (contracts/worker-jobs.md
    ExecuteTestRunJob). Idempotent against redelivery — a job for an
    already-terminal run is a no-op, same pattern as
    ai_generation.service.run_generation.

    `storage` defaults to the real settings-driven `ArtifactStorage`
    (`storage.get_storage()`) — dependency-injectable so tests can supply a
    stand-in without needing real cloud credentials, while every production
    call site (the worker job handler) gets real object storage for free by
    not overriding it.
    """
    if storage is None:
        storage = get_storage()

    async with session_scope(organization_id=str(organization_id)) as session:
        result = await session.execute(select(TestRun).where(TestRun.id == test_run_id))
        run = result.scalar_one_or_none()
        if run is None or run.status in (TestRunStatus.completed, TestRunStatus.error):
            return
        project_id = run.project_id
        initiated_by_user_id = run.initiated_by_user_id

        case_rows_result = await session.execute(
            select(TestRunCase).where(TestRunCase.test_run_id == test_run_id).order_by(TestRunCase.order_index)
        )
        run_cases = list(case_rows_result.scalars().all())

        project_result = await session.execute(select(Project).where(Project.id == project_id))
        project = project_result.scalar_one()

    await _set_run_status(
        organization_id=organization_id, test_run_id=test_run_id, status=TestRunStatus.running,
        started_at=datetime.now(UTC),
    )

    try:
        for run_case in run_cases:
            await _execute_one_case(
                organization_id=organization_id,
                test_run_id=test_run_id,
                test_case_id=run_case.test_case_id,
                target_url=project.url,
                engine=engine,
                storage=storage,
            )
        await _set_run_status(
            organization_id=organization_id, test_run_id=test_run_id, status=TestRunStatus.completed,
            completed_at=datetime.now(UTC),
        )
    except Exception:  # noqa: BLE001
        # Orchestration-level failure (not a single case's engine exception,
        # which _execute_one_case already isolates below) — still must
        # reach a terminal state rather than leave the run stuck in
        # "running" forever (NFR-007/FR-075).
        await _set_run_status(
            organization_id=organization_id, test_run_id=test_run_id, status=TestRunStatus.error,
            completed_at=datetime.now(UTC),
        )

    await _notify_run_terminal(
        organization_id=organization_id, test_run_id=test_run_id, user_id=initiated_by_user_id
    )


async def _notify_run_terminal(*, organization_id: uuid.UUID, test_run_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """FR-112/FR-113/T192: one notification per terminal run, flagged
    `run_failed_critical` instead of the plain `run_completed` when any
    failed/errored result in this run belongs to a critical-severity test
    case — the only severity signal reliably available at run-completion
    time (no issue/AI analysis exists yet for a fresh failure)."""
    async with session_scope(organization_id=str(organization_id)) as session:
        critical_failure_result = await session.execute(
            select(func.count())
            .select_from(TestResult)
            .join(TestCase, TestCase.id == TestResult.test_case_id)
            .where(
                TestResult.test_run_id == test_run_id,
                TestResult.status.in_((TestResultStatus.failed, TestResultStatus.error)),
                TestCase.severity == TestCaseSeverity.critical,
            )
        )
        has_critical_failure = critical_failure_result.scalar_one() > 0

        await notifications_service.create_notification(
            session,
            organization_id=organization_id,
            user_id=user_id,
            type=NotificationType.run_failed_critical if has_critical_failure else NotificationType.run_completed,
            related_entity_type="test_run",
            related_entity_id=test_run_id,
        )


async def _execute_one_case(
    *,
    organization_id: uuid.UUID,
    test_run_id: uuid.UUID,
    test_case_id: uuid.UUID,
    target_url: str,
    engine: BrowserAutomationEngine,
    storage: ArtifactStorage,
) -> None:
    test_result_id: uuid.UUID | None = None
    artifacts: list[CapturedArtifact] = []
    try:
        async with session_scope(organization_id=str(organization_id)) as session:
            case_result = await session.execute(select(TestCase).where(TestCase.id == test_case_id))
            test_case = case_result.scalar_one()
            steps_result = await session.execute(
                select(TestStep).where(TestStep.test_case_id == test_case_id).order_by(TestStep.order_index)
            )
            steps = list(steps_result.scalars().all())

        if not steps:
            now = datetime.now(UTC)
            await _persist_result(
                organization_id=organization_id,
                test_run_id=test_run_id,
                test_case_id=test_case_id,
                status=TestResultStatus.skipped,
                execution_log=[],
                failure_step_index=None,
                error_message="Test case has no steps to execute",
                started_at=now,
                completed_at=now,
                duration_ms=0,
            )
            return

        engine_result, artifacts = await engine.run_test_case(test_case, steps, target_url)

        test_result_id = await _persist_result(
            organization_id=organization_id,
            test_run_id=test_run_id,
            test_case_id=test_case_id,
            status=TestResultStatus(engine_result.status),
            execution_log=[
                {
                    "step_index": entry.step_index,
                    "action_type": entry.action_type,
                    "status": entry.status,
                    "message": entry.message,
                    "timestamp": entry.timestamp.isoformat(),
                }
                for entry in engine_result.execution_log
            ],
            failure_step_index=engine_result.failure_step_index,
            error_message=engine_result.error_message,
            started_at=engine_result.started_at,
            completed_at=engine_result.completed_at,
            duration_ms=engine_result.duration_ms,
        )
    except Exception as exc:  # noqa: BLE001 — FR-075/NFR-007: one case's failure never aborts the run
        now = datetime.now(UTC)
        await _persist_result(
            organization_id=organization_id,
            test_run_id=test_run_id,
            test_case_id=test_case_id,
            status=TestResultStatus.error,
            execution_log=[],
            failure_step_index=None,
            error_message=str(exc),
            started_at=now,
            completed_at=now,
            duration_ms=0,
        )
        return

    # Deliberately outside the try/except above: the TestResult (this case's
    # actual pass/fail/error outcome) is already durably persisted by this
    # point. A failure persisting artifacts must never retroactively turn a
    # correctly-recorded result into a duplicate "error" row — spec Edge
    # Cases' "the test result must still be recorded ... rather than the
    # whole test run failing" applies to storage failures specifically.
    if artifacts and test_result_id is not None:
        # Best-effort: never affects the already-recorded result.
        with contextlib.suppress(Exception):
            await _persist_artifacts(
                organization_id=organization_id, test_result_id=test_result_id, artifacts=artifacts, storage=storage
            )


async def _persist_result(
    *,
    organization_id: uuid.UUID,
    test_run_id: uuid.UUID,
    test_case_id: uuid.UUID,
    status: TestResultStatus,
    execution_log: list[dict[str, Any]],
    failure_step_index: int | None,
    error_message: str | None,
    started_at: datetime,
    completed_at: datetime,
    duration_ms: int,
) -> uuid.UUID:
    async with session_scope(organization_id=str(organization_id)) as session:
        result_row = TestResult(
            organization_id=organization_id,
            test_run_id=test_run_id,
            test_case_id=test_case_id,
            status=status,
            execution_log=execution_log,
            failure_step_index=failure_step_index,
            error_message=error_message,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
        )
        session.add(result_row)

        case_result = await session.execute(select(TestCase).where(TestCase.id == test_case_id))
        test_case = case_result.scalar_one()
        test_case.last_result = _RESULT_TO_LAST_RESULT[status]
        session.add(test_case)

        run_result = await session.execute(select(TestRun).where(TestRun.id == test_run_id))
        run = run_result.scalar_one()
        if status == TestResultStatus.passed:
            run.summary_passed += 1
        elif status == TestResultStatus.skipped:
            run.summary_skipped += 1
        else:
            run.summary_failed += 1
        session.add(run)

        await session.flush()
        await session.refresh(result_row)
        return result_row.id


async def _persist_artifacts(
    *,
    organization_id: uuid.UUID,
    test_result_id: uuid.UUID,
    artifacts: list[CapturedArtifact],
    storage: ArtifactStorage,
) -> None:
    for artifact in artifacts:
        try:
            storage_key = await storage.put(artifact.data, artifact.content_type)
        except Exception:  # noqa: BLE001 — spec Edge Cases: an upload failure must not fail the test result
            continue

        async with session_scope(organization_id=str(organization_id)) as session:
            session.add(
                Artifact(
                    organization_id=organization_id,
                    test_result_id=test_result_id,
                    type=ArtifactType.screenshot,
                    storage_key=storage_key,
                    content_type=artifact.content_type,
                    size_bytes=len(artifact.data),
                    captured_at=artifact.captured_at,
                )
            )


async def _set_run_status(
    *,
    organization_id: uuid.UUID,
    test_run_id: uuid.UUID,
    status: TestRunStatus,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
) -> None:
    async with session_scope(organization_id=str(organization_id)) as session:
        result = await session.execute(select(TestRun).where(TestRun.id == test_run_id))
        run = result.scalar_one()
        run.status = status
        if started_at is not None:
            run.started_at = started_at
        if completed_at is not None:
            run.completed_at = completed_at
        session.add(run)
