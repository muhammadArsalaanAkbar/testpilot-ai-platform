"""testpilot-cli testcases (constitution Principle II, T247).

Wraps the `testcases` library directly (not the HTTP API) — see
cli/billing.py for the pattern this follows, including the per-invocation
engine-disposal requirement explained in its `_run` docstring.
"""

import asyncio
import json
import uuid
from collections.abc import Coroutine
from typing import Any

import typer

from testpilot.core.db import dispose_engine
from testpilot.core.exceptions import TestPilotError
from testpilot.core.redis import dispose_redis
from testpilot.testcases import service
from testpilot.testcases.models import TestCase, TestCasePriority, TestCaseSeverity, TestCaseStatus

app = typer.Typer(help="Test case administration.")


def _run[T](coro: Coroutine[Any, Any, T]) -> T:
    async def _wrapped() -> T:
        try:
            return await coro
        finally:
            await dispose_engine()
            await dispose_redis()

    return asyncio.run(_wrapped())


def _to_dict(test_case: TestCase) -> dict[str, Any]:
    return {
        "id": str(test_case.id),
        "project_id": str(test_case.project_id),
        "title": test_case.title,
        "priority": test_case.priority.value,
        "severity": test_case.severity.value,
        "status": test_case.status.value,
        "source": test_case.source.value,
        "tags": test_case.tags,
    }


def _handle_error(exc: TestPilotError, json_output: bool) -> None:
    if json_output:
        typer.echo(json.dumps({"error": {"code": exc.code, "message": exc.message}}))
    else:
        typer.echo(f"Error [{exc.code}]: {exc.message}")
    raise typer.Exit(code=1) from None


@app.command("list")
def list_test_cases(
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
    status_filter: TestCaseStatus | None = typer.Option(None, "--status"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """List a project's test cases, optionally filtered by status."""
    cases = _run(
        service.list_test_cases(organization_id=organization_id, project_id=project_id, status=status_filter)
    )

    if json_output:
        typer.echo(json.dumps({"items": [_to_dict(c) for c in cases]}))
        return

    for case in cases:
        typer.echo(f"{case.id}  {case.status.value:8}  {case.priority.value:8}  {case.title}")


@app.command("create")
def create_test_case(
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
    title: str,
    description: str,
    priority: TestCasePriority = typer.Option(...),
    severity: TestCaseSeverity = typer.Option(...),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Manually create a test case (source=manual), subject to the same
    archived-project check as the HTTP API."""
    try:
        test_case, _steps = _run(
            service.create_test_case(
                organization_id=organization_id,
                project_id=project_id,
                title=title,
                description=description,
                priority=priority,
                severity=severity,
            )
        )
    except TestPilotError as exc:
        _handle_error(exc, json_output)
        return

    if json_output:
        typer.echo(json.dumps(_to_dict(test_case)))
        return
    typer.echo(f"Created test case {test_case.id}  {test_case.title}")


@app.command("approve")
def approve_test_case(
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
    test_case_id: uuid.UUID,
    json_output: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Approve a test case."""
    try:
        test_case = _run(
            service.approve_test_case(
                organization_id=organization_id, project_id=project_id, test_case_id=test_case_id
            )
        )
    except TestPilotError as exc:
        _handle_error(exc, json_output)
        return

    if json_output:
        typer.echo(json.dumps(_to_dict(test_case)))
        return
    typer.echo(f"Approved test case {test_case.id}")


@app.command("reject")
def reject_test_case(
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
    test_case_id: uuid.UUID,
    json_output: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Reject a test case (excluded from execution, retained for audit)."""
    try:
        test_case = _run(
            service.reject_test_case(
                organization_id=organization_id, project_id=project_id, test_case_id=test_case_id
            )
        )
    except TestPilotError as exc:
        _handle_error(exc, json_output)
        return

    if json_output:
        typer.echo(json.dumps(_to_dict(test_case)))
        return
    typer.echo(f"Rejected test case {test_case.id}")
