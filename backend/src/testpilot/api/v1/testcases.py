"""Test-cases routes (contracts/test-cases-api.md): library CRUD plus the
AI generation endpoints (POST .../generate, GET .../generate/{id}, POST
.../{id}/regenerate, T117)."""

import uuid

from fastapi import APIRouter, Depends, Request, status

from testpilot.ai_generation import service as ai_generation_service
from testpilot.ai_generation.models import GenerationRun, GenerationScope
from testpilot.ai_generation.schemas import GenerationRunPublic
from testpilot.api.deps import CurrentUser, get_current_user, limiter
from testpilot.api.pagination import PaginationParams
from testpilot.core.logging import current_or_new_correlation_id
from testpilot.testcases import service
from testpilot.testcases.models import (
    TestCase,
    TestCasePriority,
    TestCaseSeverity,
    TestCaseSource,
    TestCaseStatus,
    TestStep,
)
from testpilot.testcases.schemas import (
    CreateTestCaseRequest,
    TestCaseDetailResponse,
    TestCasePublic,
    TestCasesListResponse,
    TestStepInput,
    TestStepPublic,
    UpdateTestCaseRequest,
)
from testpilot.testcases.service import StepInput
from testpilot.worker.jobs.generate_test_cases import handle as generate_test_cases_job
from testpilot.worker.queues import ai_generation_queue

router = APIRouter(prefix="/projects/{project_id}/test-cases", tags=["test-cases"])


def _generation_run_to_public(run: GenerationRun) -> GenerationRunPublic:
    return GenerationRunPublic(
        id=run.id,
        project_id=run.project_id,
        scope=run.scope,
        status=run.status,
        failure_reason=run.failure_reason,
        created_test_case_ids=run.created_test_case_ids,
        created_at=run.created_at,
        completed_at=run.completed_at,
    )


def _to_public(test_case: TestCase) -> TestCasePublic:
    return TestCasePublic(
        id=test_case.id,
        project_id=test_case.project_id,
        title=test_case.title,
        description=test_case.description,
        priority=test_case.priority,
        severity=test_case.severity,
        status=test_case.status,
        source=test_case.source,
        tags=test_case.tags,
        last_result=test_case.last_result,
        created_at=test_case.created_at,
        updated_at=test_case.updated_at,
    )


def _step_to_public(step: TestStep) -> TestStepPublic:
    return TestStepPublic(
        order_index=step.order_index,
        action_type=step.action_type,
        target_descriptor=step.target_descriptor,
        input_value=step.input_value,
        expected_assertion=step.expected_assertion,
        capture_screenshot=step.capture_screenshot,
    )


def _step_to_input(step: TestStepInput) -> StepInput:
    return StepInput(
        action_type=step.action_type,
        target_descriptor=step.target_descriptor,
        input_value=step.input_value,
        expected_assertion=step.expected_assertion,
        order_index=step.order_index,
        capture_screenshot=step.capture_screenshot,
    )


@router.get("", response_model=TestCasesListResponse)
async def list_test_cases(
    project_id: uuid.UUID,
    status_filter: TestCaseStatus | None = None,
    priority: TestCasePriority | None = None,
    severity: TestCaseSeverity | None = None,
    tag: str | None = None,
    source: TestCaseSource | None = None,
    q: str | None = None,
    sort: str | None = None,
    pagination: PaginationParams = Depends(),
    current_user: CurrentUser = Depends(get_current_user),
) -> TestCasesListResponse:
    cases = await service.list_test_cases(
        organization_id=uuid.UUID(current_user.organization_id),
        project_id=project_id,
        status=status_filter,
        priority=priority,
        severity=severity,
        tag=tag,
        source=source,
        q=q,
        sort=sort,
        offset=pagination.offset,
        limit=pagination.page_size,
    )
    return TestCasesListResponse(items=[_to_public(c) for c in cases])


@router.post("", response_model=TestCasePublic, status_code=status.HTTP_201_CREATED)
async def create_test_case(
    project_id: uuid.UUID, payload: CreateTestCaseRequest, current_user: CurrentUser = Depends(get_current_user)
) -> TestCasePublic:
    test_case, _steps = await service.create_test_case(
        organization_id=uuid.UUID(current_user.organization_id),
        project_id=project_id,
        title=payload.title,
        description=payload.description,
        priority=payload.priority,
        severity=payload.severity,
        tags=payload.tags,
        steps=[_step_to_input(s) for s in payload.steps],
    )
    return _to_public(test_case)


@router.get("/{test_case_id}", response_model=TestCaseDetailResponse)
async def get_test_case(
    project_id: uuid.UUID, test_case_id: uuid.UUID, current_user: CurrentUser = Depends(get_current_user)
) -> TestCaseDetailResponse:
    test_case, steps = await service.get_test_case(
        organization_id=uuid.UUID(current_user.organization_id), project_id=project_id, test_case_id=test_case_id
    )
    return TestCaseDetailResponse(
        test_case=_to_public(test_case), steps=[_step_to_public(s) for s in steps], recent_results=[]
    )


@router.patch("/{test_case_id}", response_model=TestCasePublic)
async def update_test_case(
    project_id: uuid.UUID,
    test_case_id: uuid.UUID,
    payload: UpdateTestCaseRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> TestCasePublic:
    test_case, _steps = await service.update_test_case(
        organization_id=uuid.UUID(current_user.organization_id),
        project_id=project_id,
        test_case_id=test_case_id,
        title=payload.title,
        description=payload.description,
        priority=payload.priority,
        severity=payload.severity,
        tags=payload.tags,
        steps=[_step_to_input(s) for s in payload.steps] if payload.steps is not None else None,
    )
    return _to_public(test_case)


@router.post("/{test_case_id}/approve", response_model=TestCasePublic)
async def approve_test_case(
    project_id: uuid.UUID, test_case_id: uuid.UUID, current_user: CurrentUser = Depends(get_current_user)
) -> TestCasePublic:
    test_case = await service.approve_test_case(
        organization_id=uuid.UUID(current_user.organization_id), project_id=project_id, test_case_id=test_case_id
    )
    return _to_public(test_case)


@router.post("/{test_case_id}/reject", response_model=TestCasePublic)
async def reject_test_case(
    project_id: uuid.UUID, test_case_id: uuid.UUID, current_user: CurrentUser = Depends(get_current_user)
) -> TestCasePublic:
    test_case = await service.reject_test_case(
        organization_id=uuid.UUID(current_user.organization_id), project_id=project_id, test_case_id=test_case_id
    )
    return _to_public(test_case)


@router.delete("/{test_case_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_test_case(
    project_id: uuid.UUID, test_case_id: uuid.UUID, current_user: CurrentUser = Depends(get_current_user)
) -> None:
    await service.delete_test_case(
        organization_id=uuid.UUID(current_user.organization_id),
        project_id=project_id,
        test_case_id=test_case_id,
        actor_user_id=uuid.UUID(current_user.user_id),
    )


@router.post("/generate", response_model=GenerationRunPublic, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("10/minute")
async def generate_test_cases(
    request: Request, project_id: uuid.UUID, current_user: CurrentUser = Depends(get_current_user)
) -> GenerationRunPublic:
    run = await ai_generation_service.start_generation_run(
        organization_id=uuid.UUID(current_user.organization_id),
        project_id=project_id,
        requested_by_user_id=uuid.UUID(current_user.user_id),
    )
    ai_generation_queue().enqueue(
        generate_test_cases_job, str(run.id), str(run.organization_id), current_or_new_correlation_id()
    )
    return _generation_run_to_public(run)


@router.get("/generate/{generation_run_id}", response_model=GenerationRunPublic)
async def get_generation_run(
    project_id: uuid.UUID, generation_run_id: uuid.UUID, current_user: CurrentUser = Depends(get_current_user)
) -> GenerationRunPublic:
    run = await ai_generation_service.get_generation_run(
        organization_id=uuid.UUID(current_user.organization_id),
        project_id=project_id,
        generation_run_id=generation_run_id,
    )
    return _generation_run_to_public(run)


@router.post("/{test_case_id}/regenerate", response_model=GenerationRunPublic, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("10/minute")
async def regenerate_test_case(
    request: Request, project_id: uuid.UUID, test_case_id: uuid.UUID, current_user: CurrentUser = Depends(get_current_user)
) -> GenerationRunPublic:
    run = await ai_generation_service.start_generation_run(
        organization_id=uuid.UUID(current_user.organization_id),
        project_id=project_id,
        requested_by_user_id=uuid.UUID(current_user.user_id),
        scope=GenerationScope.single_case,
        target_test_case_id=test_case_id,
    )
    ai_generation_queue().enqueue(
        generate_test_cases_job, str(run.id), str(run.organization_id), current_or_new_correlation_id()
    )
    return _generation_run_to_public(run)
