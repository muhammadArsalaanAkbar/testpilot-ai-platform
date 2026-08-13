"""Test-runs routes (contracts/test-runs-api.md, T140)."""

import uuid

from fastapi import APIRouter, Depends, Request, status

from testpilot.ai_analysis import service as ai_analysis_service
from testpilot.ai_analysis.models import AIAnalysis
from testpilot.ai_analysis.schemas import AIAnalysisPublic
from testpilot.api.deps import CurrentUser, get_current_user, limiter
from testpilot.api.pagination import PaginationParams
from testpilot.core.logging import current_or_new_correlation_id
from testpilot.execution import service
from testpilot.execution.artifact_models import Artifact
from testpilot.execution.models import TestResult, TestRun
from testpilot.execution.schemas import (
    ArtifactPublic,
    CreateTestRunRequest,
    StepLogEntryPublic,
    TestResultDetailResponse,
    TestResultSummaryPublic,
    TestRunDetailResponse,
    TestRunListResponse,
    TestRunPublic,
)
from testpilot.storage import get_storage
from testpilot.worker.jobs.analyze_failure import handle as analyze_failure_job
from testpilot.worker.jobs.execute_test_run import handle as execute_test_run_job
from testpilot.worker.queues import ai_analysis_queue, test_execution_queue

router = APIRouter(prefix="/projects/{project_id}/test-runs", tags=["test-runs"])


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


def _result_to_public(result: TestResult) -> TestResultSummaryPublic:
    return TestResultSummaryPublic(
        id=result.id,
        test_run_id=result.test_run_id,
        test_case_id=result.test_case_id,
        status=result.status,
        failure_step_index=result.failure_step_index,
        error_message=result.error_message,
        started_at=result.started_at,
        completed_at=result.completed_at,
        duration_ms=result.duration_ms,
    )


def _artifact_to_public(artifact: Artifact, url: str | None) -> ArtifactPublic:
    return ArtifactPublic(id=artifact.id, type=artifact.type, url=url, captured_at=artifact.captured_at)


def _analysis_to_public(analysis: AIAnalysis, *, expected_vs_actual: str) -> AIAnalysisPublic:
    return AIAnalysisPublic(
        id=analysis.id,
        test_result_id=analysis.test_result_id,
        status=analysis.status.value,
        explanation=analysis.explanation,
        root_cause=analysis.root_cause,
        severity=analysis.severity,
        suggested_fix=analysis.suggested_fix,
        expected_vs_actual=expected_vs_actual,
        failure_reason=analysis.failure_reason,
        provider=analysis.provider,
        model=analysis.model,
        created_at=analysis.created_at,
    )


@router.post("", response_model=TestRunPublic, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("10/minute")
async def create_test_run(
    request: Request,
    project_id: uuid.UUID,
    payload: CreateTestRunRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> TestRunPublic:
    run = await service.create_test_run(
        organization_id=uuid.UUID(current_user.organization_id),
        project_id=project_id,
        initiated_by_user_id=uuid.UUID(current_user.user_id),
        test_case_ids=payload.test_case_ids,
    )
    test_execution_queue().enqueue(
        execute_test_run_job, str(run.id), str(run.organization_id), current_or_new_correlation_id()
    )
    return _run_to_public(run)


@router.get("", response_model=TestRunListResponse)
async def list_test_runs(
    project_id: uuid.UUID,
    pagination: PaginationParams = Depends(),
    current_user: CurrentUser = Depends(get_current_user),
) -> TestRunListResponse:
    runs, total = await service.list_test_runs(
        organization_id=uuid.UUID(current_user.organization_id),
        project_id=project_id,
        page=pagination.page,
        page_size=pagination.page_size,
    )
    return TestRunListResponse(
        items=[_run_to_public(r) for r in runs], page=pagination.page, page_size=pagination.page_size, total=total
    )


@router.get("/{test_run_id}", response_model=TestRunDetailResponse)
async def get_test_run(
    project_id: uuid.UUID, test_run_id: uuid.UUID, current_user: CurrentUser = Depends(get_current_user)
) -> TestRunDetailResponse:
    run, results = await service.get_test_run(
        organization_id=uuid.UUID(current_user.organization_id), project_id=project_id, test_run_id=test_run_id
    )
    return TestRunDetailResponse(test_run=_run_to_public(run), results=[_result_to_public(r) for r in results])


@router.get("/{test_run_id}/results/{test_result_id}", response_model=TestResultDetailResponse)
async def get_test_result(
    project_id: uuid.UUID,
    test_run_id: uuid.UUID,
    test_result_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
) -> TestResultDetailResponse:
    test_result, artifacts_with_urls = await service.get_test_result(
        organization_id=uuid.UUID(current_user.organization_id),
        project_id=project_id,
        test_run_id=test_run_id,
        test_result_id=test_result_id,
        storage=get_storage(),
    )

    ai_analyses: list[AIAnalysisPublic] = []
    if test_result.status.value == "failed":
        analyses = await ai_analysis_service.list_ai_analyses_for_result(
            organization_id=uuid.UUID(current_user.organization_id), test_result_id=test_result_id
        )
        if analyses:
            expected_vs_actual = await ai_analysis_service.get_expected_vs_actual(
                organization_id=uuid.UUID(current_user.organization_id), test_result_id=test_result_id
            )
            ai_analyses = [_analysis_to_public(a, expected_vs_actual=expected_vs_actual) for a in analyses]

    return TestResultDetailResponse(
        test_result=_result_to_public(test_result),
        execution_log=[StepLogEntryPublic(**entry) for entry in test_result.execution_log],
        artifacts=[_artifact_to_public(artifact, url) for artifact, url in artifacts_with_urls],
        ai_analyses=ai_analyses,
    )


@router.post(
    "/{test_run_id}/results/{test_result_id}/analyze",
    response_model=AIAnalysisPublic,
    status_code=status.HTTP_202_ACCEPTED,
)
@limiter.limit("10/minute")
async def analyze_result(
    request: Request,
    project_id: uuid.UUID,
    test_run_id: uuid.UUID,
    test_result_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
) -> AIAnalysisPublic:
    analysis_id = await ai_analysis_service.request_analysis(
        organization_id=uuid.UUID(current_user.organization_id),
        project_id=project_id,
        test_run_id=test_run_id,
        test_result_id=test_result_id,
        requested_by_user_id=uuid.UUID(current_user.user_id),
    )
    expected_vs_actual = await ai_analysis_service.get_expected_vs_actual(
        organization_id=uuid.UUID(current_user.organization_id), test_result_id=test_result_id
    )
    ai_analysis_queue().enqueue(
        analyze_failure_job,
        str(analysis_id),
        current_user.organization_id,
        str(test_result_id),
        current_or_new_correlation_id(),
    )
    return AIAnalysisPublic(
        id=analysis_id,
        test_result_id=test_result_id,
        status="queued",
        explanation=None,
        root_cause=None,
        severity=None,
        suggested_fix=None,
        expected_vs_actual=expected_vs_actual,
        failure_reason=None,
        provider=None,
        model=None,
        created_at=None,
    )


@router.get("/{test_run_id}/results/{test_result_id}/analyses/{analysis_id}", response_model=AIAnalysisPublic)
async def get_analysis(
    project_id: uuid.UUID,
    test_run_id: uuid.UUID,
    test_result_id: uuid.UUID,
    analysis_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
) -> AIAnalysisPublic:
    analysis = await ai_analysis_service.get_ai_analysis(
        organization_id=uuid.UUID(current_user.organization_id),
        project_id=project_id,
        test_run_id=test_run_id,
        test_result_id=test_result_id,
        analysis_id=analysis_id,
    )
    expected_vs_actual = await ai_analysis_service.get_expected_vs_actual(
        organization_id=uuid.UUID(current_user.organization_id), test_result_id=test_result_id
    )
    return _analysis_to_public(analysis, expected_vs_actual=expected_vs_actual)


@router.post("/{test_run_id}/retry-failed", response_model=TestRunPublic, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("10/minute")
async def retry_failed(
    request: Request, project_id: uuid.UUID, test_run_id: uuid.UUID, current_user: CurrentUser = Depends(get_current_user)
) -> TestRunPublic:
    run = await service.retry_failed(
        organization_id=uuid.UUID(current_user.organization_id),
        project_id=project_id,
        test_run_id=test_run_id,
        initiated_by_user_id=uuid.UUID(current_user.user_id),
    )
    test_execution_queue().enqueue(
        execute_test_run_job, str(run.id), str(run.organization_id), current_or_new_correlation_id()
    )
    return _run_to_public(run)
