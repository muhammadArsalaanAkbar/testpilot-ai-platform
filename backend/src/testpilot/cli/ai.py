"""testpilot-cli ai (constitution Principle II, T249/T253).

Wraps `ai_generation`/`ai_analysis` directly (not the HTTP API) — see
cli/billing.py for the pattern this follows, including the per-invocation
engine-disposal requirement explained in its `_run` docstring.
`generate-tests`/`analyze` both enqueue onto the same real Redis queues the
HTTP routes use (worker/queues.py) — each command's own scope is "validate,
reserve, and enqueue," matching plan.md's Async Job Lifecycle step 1; a real
worker process (or a direct `run_generation`/`run_analysis` call, e.g. in
tests) still has to process the job for it to complete.
"""

import asyncio
import json
import uuid
from collections.abc import Coroutine
from typing import Any

import typer

from testpilot.ai_analysis import service as ai_analysis_service
from testpilot.ai_generation import service
from testpilot.ai_generation.models import GenerationRun
from testpilot.core.db import dispose_engine
from testpilot.core.exceptions import TestPilotError
from testpilot.core.logging import current_or_new_correlation_id
from testpilot.core.redis import dispose_redis
from testpilot.worker.jobs.analyze_failure import handle as analyze_failure_job
from testpilot.worker.jobs.generate_test_cases import handle as generate_test_cases_job
from testpilot.worker.queues import ai_analysis_queue, ai_generation_queue

app = typer.Typer(help="AI generation and analysis administration.")


def _run[T](coro: Coroutine[Any, Any, T]) -> T:
    async def _wrapped() -> T:
        try:
            return await coro
        finally:
            await dispose_engine()
            await dispose_redis()

    return asyncio.run(_wrapped())


def _to_dict(run: GenerationRun) -> dict[str, Any]:
    return {
        "id": str(run.id),
        "project_id": str(run.project_id),
        "scope": run.scope.value,
        "status": run.status.value,
        "failure_reason": run.failure_reason,
        "created_test_case_ids": [str(i) for i in run.created_test_case_ids],
    }


@app.command("generate-tests")
def generate_tests(
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
    requested_by_user_id: uuid.UUID,
    json_output: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Enqueue a full-batch test-case generation job for a project."""
    try:
        run = _run(
            service.start_generation_run(
                organization_id=organization_id,
                project_id=project_id,
                requested_by_user_id=requested_by_user_id,
            )
        )
    except TestPilotError as exc:
        if json_output:
            typer.echo(json.dumps({"error": {"code": exc.code, "message": exc.message}}))
        else:
            typer.echo(f"Error [{exc.code}]: {exc.message}")
        raise typer.Exit(code=1) from None

    ai_generation_queue().enqueue(
        generate_test_cases_job, str(run.id), str(run.organization_id), current_or_new_correlation_id()
    )

    if json_output:
        typer.echo(json.dumps(_to_dict(run)))
        return
    typer.echo(f"Enqueued generation run {run.id} (status={run.status.value})")


@app.command("analyze")
def analyze(
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
    test_run_id: uuid.UUID,
    test_result_id: uuid.UUID,
    requested_by_user_id: uuid.UUID,
    json_output: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Request AI failure analysis for a failed test result (T253)."""
    try:
        analysis_id = _run(
            ai_analysis_service.request_analysis(
                organization_id=organization_id,
                project_id=project_id,
                test_run_id=test_run_id,
                test_result_id=test_result_id,
                requested_by_user_id=requested_by_user_id,
            )
        )
    except TestPilotError as exc:
        if json_output:
            typer.echo(json.dumps({"error": {"code": exc.code, "message": exc.message}}))
        else:
            typer.echo(f"Error [{exc.code}]: {exc.message}")
        raise typer.Exit(code=1) from None

    ai_analysis_queue().enqueue(
        analyze_failure_job,
        str(analysis_id),
        str(organization_id),
        str(test_result_id),
        current_or_new_correlation_id(),
    )

    if json_output:
        typer.echo(json.dumps({"id": str(analysis_id), "test_result_id": str(test_result_id), "status": "queued"}))
        return
    typer.echo(f"Enqueued AI analysis {analysis_id} (status=queued) for result {test_result_id}")
