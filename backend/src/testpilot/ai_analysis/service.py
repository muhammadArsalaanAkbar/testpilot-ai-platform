"""AI failure analysis orchestration (FR-079-FR-086, FR-123-FR-125, T160/T163).

Same three-step async-job shape ai_generation/service.py and execution/
service.py+runner.py use: `request_analysis` here is the validate-and-reserve
step (result-is-failed check, ai_operations plan-limit reservation) called
by the route (T161) before it enqueues; `run_analysis` is the actual work
(context assembly -> provider call -> persist), invoked by the worker job
handler (T162) and directly by tests/CLI without needing a real queue.

Unlike generation_runs/test_runs, no row is created at "queued" time — see
ai_analysis/models.py's module docstring for why data-model.md's 2-value
status enum (completed/failed only) makes that the correct design here, not
an oversight to work around.

Notification writing (worker-jobs.md's "write a notifications row",
T192/FR-114) happens inside `run_analysis`'s own final session, notifying
the test run's initiator — the job payload carries no separate requesting-
user id (contracts/worker-jobs.md AnalyzeFailureJob), so the run initiator
is the only user reliably associable with the result at this point.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from testpilot.ai_analysis.models import AIAnalysis, AIAnalysisStatus, AnalysisSeverity
from testpilot.ai_provider.base import AIProviderError, FailureContext, LLMProvider
from testpilot.billing import service as billing_service
from testpilot.core.db import session_scope
from testpilot.core.exceptions import ConflictError, NotFoundError
from testpilot.execution.artifact_models import Artifact, ArtifactType
from testpilot.execution.models import TestResult, TestResultStatus, TestRun
from testpilot.notifications import service as notifications_service
from testpilot.notifications.models import NotificationType
from testpilot.storage import get_storage
from testpilot.storage.base import ArtifactStorage
from testpilot.testcases.models import TestStep

# FR-083: bounded retry — one retry (two attempts total) for a *retryable*
# provider error, matching plan.md's "e.g., 2 retries" note. No sleep/
# backoff between attempts: the provider adapter itself already enforces a
# request timeout (contracts/ai-provider-adapter.md), so a second immediate
# attempt is a reasonable bounded policy without slowing every analysis
# (and every test of this path) down with an artificial delay.
_MAX_ATTEMPTS = 2

_ARTIFACT_URL_EXPIRES_IN_SECONDS = 300


class ResultNotFailedError(ConflictError):
    """FR-079: AI analysis may only be requested for a failed test result."""

    code = "result_not_failed"


async def _get_result_or_404(
    session: AsyncSession, *, organization_id: uuid.UUID, project_id: uuid.UUID, test_run_id: uuid.UUID, test_result_id: uuid.UUID
) -> TestResult:
    run_result = await session.execute(
        select(TestRun).where(
            TestRun.id == test_run_id, TestRun.project_id == project_id, TestRun.organization_id == organization_id
        )
    )
    if run_result.scalar_one_or_none() is None:
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
    return test_result


async def _failing_step(session: AsyncSession, test_result: TestResult) -> TestStep | None:
    if test_result.failure_step_index is None:
        return None
    result = await session.execute(
        select(TestStep).where(
            TestStep.test_case_id == test_result.test_case_id, TestStep.order_index == test_result.failure_step_index
        )
    )
    return result.scalar_one_or_none()


def _log_entry_for_step(test_result: TestResult, step_index: int) -> dict[str, object] | None:
    return next((e for e in test_result.execution_log if e.get("step_index") == step_index), None)


def _format_expected_vs_actual(test_result: TestResult, test_step: TestStep | None) -> str:
    if test_result.failure_step_index is None:
        return "No specific step failure was recorded for this result."
    log_entry = _log_entry_for_step(test_result, test_result.failure_step_index)
    actual = (log_entry or {}).get("message") or test_result.error_message or "No further detail was recorded."
    expected = (test_step.expected_assertion if test_step else None) or "the step to complete without error"
    return f"Expected: {expected}\nActual: {actual}"


def _format_execution_log(test_result: TestResult) -> list[str]:
    formatted = []
    for entry in test_result.execution_log:
        step_index = entry.get("step_index")
        action_type = entry.get("action_type")
        status = entry.get("status")
        message = entry.get("message")
        line = f"Step {step_index} ({action_type}): {status}"
        if message:
            line += f" — {message}"
        formatted.append(line)
    return formatted


async def get_expected_vs_actual(*, organization_id: uuid.UUID, test_result_id: uuid.UUID) -> str:
    """Re-derived from the always-persisted TestResult/TestStep data (never
    stored on the AIAnalysis row itself — FR-082 doesn't require an AI
    narrative for this, just that it's explicitly presented, and it can be
    computed fresh regardless of whether analysis ever ran or succeeded)."""
    async with session_scope(organization_id=str(organization_id)) as session:
        result = await session.execute(
            select(TestResult).where(TestResult.id == test_result_id, TestResult.organization_id == organization_id)
        )
        test_result = result.scalar_one()
        test_step = await _failing_step(session, test_result)
        return _format_expected_vs_actual(test_result, test_step)


async def request_analysis(
    *,
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
    test_run_id: uuid.UUID,
    test_result_id: uuid.UUID,
    requested_by_user_id: uuid.UUID,
) -> uuid.UUID:
    """The validate-and-reserve step (FR-079, FR-123). Returns a freshly
    generated analysis id — not yet backed by any row (see module
    docstring) — for the caller to enqueue `AnalyzeFailureJob` with."""
    async with session_scope(organization_id=str(organization_id)) as session:
        test_result = await _get_result_or_404(
            session, organization_id=organization_id, project_id=project_id, test_run_id=test_run_id,
            test_result_id=test_result_id,
        )
        if test_result.status != TestResultStatus.failed:
            raise ResultNotFailedError("AI analysis can only be requested for a failed test result")

    # FR-123-FR-125: plan-limit check outside the read transaction above,
    # same ordering ai_generation/execution use.
    await billing_service.check_and_reserve_period_usage(organization_id=organization_id, metric="ai_operations")

    return uuid.uuid4()


async def run_analysis(
    *,
    ai_analysis_id: uuid.UUID,
    organization_id: uuid.UUID,
    test_result_id: uuid.UUID,
    provider: LLMProvider,
    storage: ArtifactStorage | None,
) -> None:
    """Handler-contract implementation (contracts/worker-jobs.md
    AnalyzeFailureJob). Idempotent against redelivery — a job whose analysis
    id already has a row is a no-op, same pattern as ai_generation/execution.
    """
    if storage is None:
        storage = get_storage()

    async with session_scope(organization_id=str(organization_id)) as session:
        existing = await session.execute(select(AIAnalysis).where(AIAnalysis.id == ai_analysis_id))
        if existing.scalar_one_or_none() is not None:
            return

        result = await session.execute(
            select(TestResult).where(TestResult.id == test_result_id, TestResult.organization_id == organization_id)
        )
        test_result = result.scalar_one()
        test_run_id = test_result.test_run_id
        test_step = await _failing_step(session, test_result)

        screenshot_artifact: Artifact | None = None
        if test_result.failure_step_index is not None:
            artifact_result = await session.execute(
                select(Artifact)
                .where(
                    Artifact.test_result_id == test_result_id,
                    Artifact.type == ArtifactType.screenshot,
                    Artifact.storage_key.is_not(None),
                )
                .order_by(Artifact.captured_at.desc())
            )
            screenshot_artifact = artifact_result.scalars().first()

    # SEC-012/FR-086: the screenshot handed to the provider is a short-lived
    # signed URL scoped to this Organization's own artifact — never a raw
    # bucket path/credential, and never another Organization's data (the
    # query above is itself organization_id-scoped).
    screenshot_reference = ""
    if screenshot_artifact is not None and screenshot_artifact.storage_key is not None:
        try:
            screenshot_reference = await storage.get_url(
                screenshot_artifact.storage_key, expires_in=_ARTIFACT_URL_EXPIRES_IN_SECONDS
            )
        except Exception:  # noqa: BLE001 — FR-080's screenshot input is best-effort, not a hard blocker
            screenshot_reference = ""

    context = FailureContext(
        step_action_type=test_step.action_type if test_step else "assert_content",
        step_target_descriptor=test_step.target_descriptor if test_step else None,
        step_expected_assertion=test_step.expected_assertion if test_step else None,
        actual_state=test_result.error_message or "",
        execution_log=_format_execution_log(test_result),
        screenshot_reference=screenshot_reference,
    )

    analysis = None
    failure_reason: str | None = None
    for attempt in range(_MAX_ATTEMPTS):
        try:
            analysis = await provider.analyze_failure(context)
            break
        except AIProviderError as exc:
            failure_reason = str(exc)
            if not exc.retryable or attempt == _MAX_ATTEMPTS - 1:
                break

    async with session_scope(organization_id=str(organization_id)) as session:
        if analysis is not None:
            row = AIAnalysis(
                id=ai_analysis_id,
                organization_id=organization_id,
                test_result_id=test_result_id,
                status=AIAnalysisStatus.completed,
                explanation=analysis.explanation,
                root_cause=analysis.root_cause,
                severity=AnalysisSeverity(analysis.severity),
                suggested_fix=analysis.suggested_fix,
                provider=provider.provider_name,
                model=provider.model,
                created_at=datetime.now(UTC),
            )
        else:
            row = AIAnalysis(
                id=ai_analysis_id,
                organization_id=organization_id,
                test_result_id=test_result_id,
                status=AIAnalysisStatus.failed,
                failure_reason=failure_reason or "AI analysis failed for an unknown reason",
                provider=provider.provider_name,
                model=provider.model,
                created_at=datetime.now(UTC),
            )
        session.add(row)

        # FR-114/T192: the job payload (contracts/worker-jobs.md
        # AnalyzeFailureJob) deliberately carries no requesting-user id, so
        # the only user reliably associable with this result at this point
        # is whoever started the test run it belongs to.
        run_result = await session.execute(select(TestRun.initiated_by_user_id).where(TestRun.id == test_run_id))
        initiated_by_user_id = run_result.scalar_one()
        await notifications_service.create_notification(
            session,
            organization_id=organization_id,
            user_id=initiated_by_user_id,
            type=NotificationType.ai_analysis_completed if analysis is not None else NotificationType.ai_analysis_failed,
            related_entity_type="test_result",
            related_entity_id=test_result_id,
        )


async def get_ai_analysis(
    *,
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
    test_run_id: uuid.UUID,
    test_result_id: uuid.UUID,
    analysis_id: uuid.UUID,
) -> AIAnalysis:
    async with session_scope(organization_id=str(organization_id)) as session:
        await _get_result_or_404(
            session, organization_id=organization_id, project_id=project_id, test_run_id=test_run_id,
            test_result_id=test_result_id,
        )
        result = await session.execute(
            select(AIAnalysis).where(
                AIAnalysis.id == analysis_id,
                AIAnalysis.test_result_id == test_result_id,
                AIAnalysis.organization_id == organization_id,
            )
        )
        analysis = result.scalar_one_or_none()
        if analysis is None:
            raise NotFoundError("AI analysis not found")
        return analysis


async def list_ai_analyses_for_result(*, organization_id: uuid.UUID, test_result_id: uuid.UUID) -> list[AIAnalysis]:
    async with session_scope(organization_id=str(organization_id)) as session:
        result = await session.execute(
            select(AIAnalysis)
            .where(AIAnalysis.test_result_id == test_result_id, AIAnalysis.organization_id == organization_id)
            .order_by(AIAnalysis.created_at.desc())
        )
        return list(result.scalars().all())
