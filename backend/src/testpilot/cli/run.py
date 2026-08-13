"""testpilot-cli run execute/list/retry-failed (constitution Principle II, T251).

Wraps the `execution` library directly (not the HTTP API) — see cli/billing.py
for the pattern this follows, including the per-invocation engine-disposal
requirement explained in its `_run` docstring. `execute` enqueues onto the
same real Redis queue the HTTP route uses (worker/queues.py) — this CLI
command's own scope is "validate, reserve, and enqueue," matching plan.md's
Async Job Lifecycle step 1; a real worker process (or a direct
`execution.runner.run_test_run` call, e.g. in tests) still has to process
the job for it to complete.
"""

import asyncio
import json
import uuid
from collections.abc import Coroutine
from typing import Any

import typer

from testpilot.core.db import dispose_engine
from testpilot.core.exceptions import TestPilotError
from testpilot.core.logging import current_or_new_correlation_id
from testpilot.core.redis import dispose_redis
from testpilot.execution import service
from testpilot.execution.models import TestRun
from testpilot.worker.jobs.execute_test_run import handle as execute_test_run_job
from testpilot.worker.queues import test_execution_queue

app = typer.Typer(help="Test-run administration.")


def _run[T](coro: Coroutine[Any, Any, T]) -> T:
    async def _wrapped() -> T:
        try:
            return await coro
        finally:
            await dispose_engine()
            await dispose_redis()

    return asyncio.run(_wrapped())


def _to_dict(run: TestRun) -> dict[str, Any]:
    return {
        "id": str(run.id),
        "project_id": str(run.project_id),
        "status": run.status.value,
        "summary_total": run.summary_total,
        "summary_passed": run.summary_passed,
        "summary_failed": run.summary_failed,
        "summary_skipped": run.summary_skipped,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
    }


@app.command("execute")
def execute(
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
    requested_by_user_id: uuid.UUID,
    test_case_ids: list[uuid.UUID] = typer.Argument(..., help="One or more test case IDs to run."),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Start a test run against the given project's configured URL."""
    try:
        run = _run(
            service.create_test_run(
                organization_id=organization_id,
                project_id=project_id,
                initiated_by_user_id=requested_by_user_id,
                test_case_ids=test_case_ids,
            )
        )
    except TestPilotError as exc:
        if json_output:
            typer.echo(json.dumps({"error": {"code": exc.code, "message": exc.message}}))
        else:
            typer.echo(f"Error [{exc.code}]: {exc.message}")
        raise typer.Exit(code=1) from None

    test_execution_queue().enqueue(
        execute_test_run_job, str(run.id), str(run.organization_id), current_or_new_correlation_id()
    )

    if json_output:
        typer.echo(json.dumps(_to_dict(run)))
        return
    typer.echo(f"Enqueued test run {run.id} (status={run.status.value})")


@app.command("list")
def list_runs(
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
    page: int = typer.Option(1, "--page"),
    page_size: int = typer.Option(25, "--page-size"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """List a project's test runs, most recent first."""
    runs, total = _run(
        service.list_test_runs(
            organization_id=organization_id, project_id=project_id, page=page, page_size=page_size
        )
    )

    if json_output:
        typer.echo(json.dumps({"items": [_to_dict(r) for r in runs], "page": page, "page_size": page_size, "total": total}))
        return

    for run in runs:
        typer.echo(
            f"{run.id}  {run.status.value:9}  "
            f"passed={run.summary_passed} failed={run.summary_failed} "
            f"skipped={run.summary_skipped} total={run.summary_total}"
        )


@app.command("retry-failed")
def retry_failed(
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
    test_run_id: uuid.UUID,
    requested_by_user_id: uuid.UUID,
    json_output: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Start a new run scoped to only the failed cases from a completed run."""
    try:
        run = _run(
            service.retry_failed(
                organization_id=organization_id,
                project_id=project_id,
                test_run_id=test_run_id,
                initiated_by_user_id=requested_by_user_id,
            )
        )
    except TestPilotError as exc:
        if json_output:
            typer.echo(json.dumps({"error": {"code": exc.code, "message": exc.message}}))
        else:
            typer.echo(f"Error [{exc.code}]: {exc.message}")
        raise typer.Exit(code=1) from None

    test_execution_queue().enqueue(
        execute_test_run_job, str(run.id), str(run.organization_id), current_or_new_correlation_id()
    )

    if json_output:
        typer.echo(json.dumps(_to_dict(run)))
        return
    typer.echo(f"Enqueued retry test run {run.id} (status={run.status.value})")
