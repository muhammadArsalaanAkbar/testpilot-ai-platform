"""T217/T218: correlation_id propagation from the API request into the
worker job envelope (contracts/worker-jobs.md's shared envelope), and the
job-duration/error-rate metrics (NFR-011) each handler records around the
same call. Each job handler's `_handle_async` must bind the passed-through
correlation_id into the logging context (core/logging.py) before doing any
work, so every log statement made during that job's execution — including
deep in the service layer — carries the same correlation_id the
originating API request logged under; and must record a
`testpilot_jobs_total{status="failure"}` outcome (core/metrics.py) when the
underlying service call raises, so a genuine job-level error (as opposed
to a per-test-case/per-item failure the service already handles
internally, per each contract's own retry/idempotency section) counts
toward NFR-011's error-rate metric.

Exercises `_handle_async` directly rather than the full `handle(...)` ->
`asyncio.run(...)` bridge, and stubs out the expensive collaborators
(PlaywrightEngine, ai_generation_service.run_generation, etc.) — this test
is about the envelope/context-binding/metrics plumbing itself, not about
generation/execution/analysis correctness, which their own dedicated
tests already cover.
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from testpilot.core.logging import correlation_id_var
from testpilot.core.metrics import jobs_total

pytestmark = pytest.mark.anyio


async def test_execute_test_run_job_binds_correlation_id():
    from testpilot.worker.jobs import execute_test_run

    test_run_id = uuid.uuid4()
    organization_id = uuid.uuid4()
    seen_correlation_id: list[str | None] = []

    async def _fake_run_test_run(**kwargs: object) -> None:
        seen_correlation_id.append(correlation_id_var.get())

    with (
        patch("testpilot.worker.jobs.execute_test_run.runner.run_test_run", side_effect=_fake_run_test_run),
        patch("testpilot.worker.jobs.execute_test_run.PlaywrightEngine") as mock_engine_cls,
        patch("testpilot.worker.jobs.execute_test_run.dispose_engine", new_callable=AsyncMock),
    ):
        mock_engine_cls.return_value.close = AsyncMock()
        await execute_test_run._handle_async(test_run_id, organization_id, "corr-execute-123")

    assert seen_correlation_id == ["corr-execute-123"]


async def test_generate_test_cases_job_binds_correlation_id():
    from testpilot.worker.jobs import generate_test_cases

    generation_run_id = uuid.uuid4()
    organization_id = uuid.uuid4()
    seen_correlation_id: list[str | None] = []

    async def _fake_run_generation(**kwargs: object) -> None:
        seen_correlation_id.append(correlation_id_var.get())

    with (
        patch(
            "testpilot.worker.jobs.generate_test_cases.ai_generation_service.run_generation",
            side_effect=_fake_run_generation,
        ),
        patch("testpilot.worker.jobs.generate_test_cases.get_provider"),
        patch("testpilot.worker.jobs.generate_test_cases.PlaywrightEngine") as mock_engine_cls,
        patch("testpilot.worker.jobs.generate_test_cases.dispose_engine", new_callable=AsyncMock),
    ):
        mock_engine_cls.return_value.close = AsyncMock()
        await generate_test_cases._handle_async(generation_run_id, organization_id, "corr-generate-456")

    assert seen_correlation_id == ["corr-generate-456"]


async def test_analyze_failure_job_binds_correlation_id():
    from testpilot.worker.jobs import analyze_failure

    ai_analysis_id = uuid.uuid4()
    organization_id = uuid.uuid4()
    test_result_id = uuid.uuid4()
    seen_correlation_id: list[str | None] = []

    async def _fake_run_analysis(**kwargs: object) -> None:
        seen_correlation_id.append(correlation_id_var.get())

    with (
        patch(
            "testpilot.worker.jobs.analyze_failure.ai_analysis_service.run_analysis",
            side_effect=_fake_run_analysis,
        ),
        patch("testpilot.worker.jobs.analyze_failure.get_provider"),
        patch("testpilot.worker.jobs.analyze_failure.dispose_engine", new_callable=AsyncMock),
    ):
        await analyze_failure._handle_async(
            ai_analysis_id, organization_id, test_result_id, "corr-analyze-789"
        )

    assert seen_correlation_id == ["corr-analyze-789"]


async def test_execute_test_run_job_records_a_failure_metric_when_the_runner_raises():
    from testpilot.worker.jobs import execute_test_run

    before = jobs_total.labels(job_type="test-execution", status="failure")._value.get()

    with (
        patch(
            "testpilot.worker.jobs.execute_test_run.runner.run_test_run",
            side_effect=RuntimeError("boom"),
        ),
        patch("testpilot.worker.jobs.execute_test_run.PlaywrightEngine") as mock_engine_cls,
        patch("testpilot.worker.jobs.execute_test_run.dispose_engine", new_callable=AsyncMock),
    ):
        mock_engine_cls.return_value.close = AsyncMock()
        with pytest.raises(RuntimeError):
            await execute_test_run._handle_async(uuid.uuid4(), uuid.uuid4(), "corr-fail")

    after = jobs_total.labels(job_type="test-execution", status="failure")._value.get()
    assert after == before + 1


async def test_execute_test_run_job_records_a_success_metric_on_the_happy_path():
    from testpilot.worker.jobs import execute_test_run

    before = jobs_total.labels(job_type="test-execution", status="success")._value.get()

    with (
        patch("testpilot.worker.jobs.execute_test_run.runner.run_test_run", new_callable=AsyncMock),
        patch("testpilot.worker.jobs.execute_test_run.PlaywrightEngine") as mock_engine_cls,
        patch("testpilot.worker.jobs.execute_test_run.dispose_engine", new_callable=AsyncMock),
    ):
        mock_engine_cls.return_value.close = AsyncMock()
        await execute_test_run._handle_async(uuid.uuid4(), uuid.uuid4(), "corr-success")

    after = jobs_total.labels(job_type="test-execution", status="success")._value.get()
    assert after == before + 1
