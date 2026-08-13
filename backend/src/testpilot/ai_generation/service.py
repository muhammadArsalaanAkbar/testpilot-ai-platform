"""AI test-case generation orchestration (FR-036-FR-047, FR-123-FR-125, DATA-006).

The three-step async-job shape (validate+enqueue -> worker executes+persists
-> notify, plan.md's Async Job Lifecycle) is split across:
- `start_generation_run` here: the DB-side validate-and-reserve step (plan
  limit check, FR-047 concurrency guard, `queued` row) — called by the route
  (T117) before it enqueues onto the Redis queue.
- `run_generation` here: the actual work (site analysis -> AI call ->
  persist draft test cases), invoked by the worker job handler (T118), and
  directly by tests/CLI without needing a real queue.

Notification writing (worker-jobs.md's "write a notifications row") is
deferred to Phase 17, which builds the `notifications` table/library —
nothing to call yet, same deferred-dependency pattern used elsewhere this
build (e.g. projects/service.py's cascading-delete note).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from testpilot.ai_generation.analysis import NoPublicContentError, analyze_site
from testpilot.ai_generation.models import GenerationRun, GenerationScope, GenerationStatus
from testpilot.ai_provider.base import AIProviderError, LLMProvider
from testpilot.billing import service as billing_service
from testpilot.core.db import session_scope
from testpilot.core.exceptions import ConflictError, NotFoundError, ProjectArchivedError
from testpilot.execution.engine import BrowserAutomationEngine
from testpilot.projects.models import Project, ProjectStatus
from testpilot.testcases import service as testcases_service
from testpilot.testcases.models import TestCase, TestCaseSource, TestCaseStatus
from testpilot.testcases.service import StepInput


class GenerationInProgressError(ConflictError):
    """FR-047: a generation job is already queued/running for this project."""

    code = "generation_in_progress"


async def _get_project_or_404(organization_id: uuid.UUID, project_id: uuid.UUID) -> Project:
    async with session_scope(organization_id=str(organization_id)) as session:
        result = await session.execute(
            select(Project).where(Project.id == project_id, Project.organization_id == organization_id)
        )
        project = result.scalar_one_or_none()
        if project is None:
            raise NotFoundError("Project not found")
        return project


async def start_generation_run(
    *,
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
    requested_by_user_id: uuid.UUID,
    scope: GenerationScope = GenerationScope.full_batch,
    target_test_case_id: uuid.UUID | None = None,
) -> GenerationRun:
    project = await _get_project_or_404(organization_id, project_id)
    if project.status == ProjectStatus.archived:
        raise ProjectArchivedError("Cannot generate test cases for an archived project")

    # FR-123-FR-125: plan-limit check before enqueueing (plan.md Async Job
    # Lifecycle step 1) — raises PlanLimitExceededError (402) if exceeded.
    await billing_service.check_and_reserve_period_usage(organization_id=organization_id, metric="ai_operations")

    async with session_scope(organization_id=str(organization_id)) as session:
        # FR-047: one project may not have two concurrent generation jobs.
        existing = await session.execute(
            select(GenerationRun).where(
                GenerationRun.project_id == project_id,
                GenerationRun.status.in_([GenerationStatus.queued, GenerationStatus.running]),
            )
        )
        in_progress = existing.scalar_one_or_none()
        if in_progress is not None:
            raise GenerationInProgressError(
                "A generation job is already in progress for this project",
                details={"generation_run_id": str(in_progress.id)},
            )

        run = GenerationRun(
            organization_id=organization_id,
            project_id=project_id,
            requested_by_user_id=requested_by_user_id,
            scope=scope,
            target_test_case_id=target_test_case_id,
            status=GenerationStatus.queued,
        )
        session.add(run)
        await session.flush()
        await session.refresh(run)
        return run


async def get_generation_run(
    *, organization_id: uuid.UUID, project_id: uuid.UUID, generation_run_id: uuid.UUID
) -> GenerationRun:
    async with session_scope(organization_id=str(organization_id)) as session:
        result = await session.execute(
            select(GenerationRun).where(
                GenerationRun.id == generation_run_id,
                GenerationRun.project_id == project_id,
                GenerationRun.organization_id == organization_id,
            )
        )
        run = result.scalar_one_or_none()
        if run is None:
            raise NotFoundError("Generation run not found")
        return run


async def _set_run_status(
    *,
    organization_id: uuid.UUID,
    generation_run_id: uuid.UUID,
    status: GenerationStatus,
    failure_reason: str | None = None,
    created_test_case_ids: list[uuid.UUID] | None = None,
) -> None:
    async with session_scope(organization_id=str(organization_id)) as session:
        result = await session.execute(select(GenerationRun).where(GenerationRun.id == generation_run_id))
        run = result.scalar_one()
        run.status = status
        run.failure_reason = failure_reason
        if created_test_case_ids is not None:
            run.created_test_case_ids = created_test_case_ids
        if status in (GenerationStatus.completed, GenerationStatus.failed):
            run.completed_at = datetime.now(UTC)
        session.add(run)


async def run_generation(
    *, generation_run_id: uuid.UUID, organization_id: uuid.UUID, provider: LLMProvider, engine: BrowserAutomationEngine
) -> None:
    """Handler-contract implementation (contracts/worker-jobs.md
    GenerateTestCasesJob): sets status=running, does the work, persists
    results exactly as returned (DATA-006, no silent mutation before
    review), sets status=completed/failed. Idempotent against redelivery —
    a job for an already-terminal run is a no-op.

    `organization_id` is taken from the caller (the shared job envelope
    carries it alongside `generation_run_id` — worker-jobs.md) rather than
    discovered by reading the row first: every tenant table (including
    generation_runs) has RLS FORCEd even for the app role, so a read with no
    `app.current_org_id` set returns zero rows, not "any org" — there is no
    unscoped bootstrap read to fall back on here.
    """
    async with session_scope(organization_id=str(organization_id)) as session:
        result = await session.execute(select(GenerationRun).where(GenerationRun.id == generation_run_id))
        run = result.scalar_one_or_none()
        if run is None or run.status in (GenerationStatus.completed, GenerationStatus.failed):
            return
        project_id = run.project_id
        scope = run.scope
        target_test_case_id = run.target_test_case_id

    await _set_run_status(organization_id=organization_id, generation_run_id=generation_run_id, status=GenerationStatus.running)

    try:
        project = await _get_project_or_404(organization_id, project_id)
        context = await analyze_site(
            engine=engine, project_name=project.name, base_url=project.url, preferences=project.settings or {}
        )
        batch = await provider.generate_test_cases(context)
        created_test_case_ids: list[uuid.UUID] = []

        if scope == GenerationScope.single_case:
            if not batch.test_cases or target_test_case_id is None:
                raise AIProviderError("AI provider returned no test case to regenerate with", retryable=False)
            generated = batch.test_cases[0]
            await testcases_service.update_test_case(
                organization_id=organization_id,
                project_id=project_id,
                test_case_id=target_test_case_id,
                title=generated.title,
                description=generated.description,
                priority=generated.priority,
                severity=generated.severity,
                steps=[
                    StepInput(
                        action_type=step.action_type,
                        target_descriptor=step.target_descriptor,
                        input_value=step.input_value,
                        expected_assertion=step.expected_assertion,
                    )
                    for step in generated.steps
                ],
            )
            # Regenerated content differs from whatever was last reviewed —
            # it goes back to draft for re-review, same as any other newly
            # generated case (FR-041/FR-042's review loop).
            async with session_scope(organization_id=str(organization_id)) as session:
                case_result = await session.execute(select(TestCase).where(TestCase.id == target_test_case_id))
                test_case = case_result.scalar_one()
                test_case.status = TestCaseStatus.draft
                session.add(test_case)
            created_test_case_ids = [target_test_case_id]
        else:
            for generated in batch.test_cases:
                created_case, _steps = await testcases_service.create_test_case(
                    organization_id=organization_id,
                    project_id=project_id,
                    title=generated.title,
                    description=generated.description,
                    priority=generated.priority,
                    severity=generated.severity,
                    steps=[
                        StepInput(
                            action_type=step.action_type,
                            target_descriptor=step.target_descriptor,
                            input_value=step.input_value,
                            expected_assertion=step.expected_assertion,
                        )
                        for step in generated.steps
                    ],
                    source=TestCaseSource.ai_generated,
                )
                created_test_case_ids.append(created_case.id)

        await _set_run_status(
            organization_id=organization_id,
            generation_run_id=generation_run_id,
            status=GenerationStatus.completed,
            created_test_case_ids=created_test_case_ids,
        )
    except (NoPublicContentError, AIProviderError) as exc:
        await _set_run_status(
            organization_id=organization_id,
            generation_run_id=generation_run_id,
            status=GenerationStatus.failed,
            failure_reason=str(exc),
        )
