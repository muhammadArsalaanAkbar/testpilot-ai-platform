"""testpilot-cli reports (constitution Principle II, T255).

Wraps the `reports` library directly (not the HTTP API) — see cli/billing.py
for the pattern this follows, including the per-invocation engine-disposal
requirement explained in its `_run` docstring.
"""

import asyncio
import json
import uuid
from collections.abc import Coroutine
from datetime import date
from typing import Any

import typer

from testpilot.core.db import dispose_engine
from testpilot.core.exceptions import TestPilotError
from testpilot.core.redis import dispose_redis
from testpilot.reports import service

app = typer.Typer(help="Project reporting.")


@app.callback()
def _callback() -> None:
    """Project reporting.

    A no-op callback exists solely so Typer keeps subcommand dispatch
    (`reports summary ...`) even with only one command registered — with
    zero registered callbacks, Typer collapses a single-command app into a
    bare command with no subcommand name at all (see typer.main.get_command).
    """


def _run[T](coro: Coroutine[Any, Any, T]) -> T:
    async def _wrapped() -> T:
        try:
            return await coro
        finally:
            await dispose_engine()
            await dispose_redis()

    return asyncio.run(_wrapped())


def _handle_error(exc: TestPilotError, json_output: bool) -> None:
    if json_output:
        typer.echo(json.dumps({"error": {"code": exc.code, "message": exc.message}}))
    else:
        typer.echo(f"Error [{exc.code}]: {exc.message}")
    raise typer.Exit(code=1) from None


@app.command("summary")
def summary(
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
    from_: str | None = typer.Option(None, "--from", help="ISO date, e.g. 2026-01-01."),
    to: str | None = typer.Option(None, "--to", help="ISO date, e.g. 2026-01-31."),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Show a project's totals, pass/failure percentage, and coverage for a date range (default: last 30 days)."""
    from_date = date.fromisoformat(from_) if from_ else None
    to_date = date.fromisoformat(to) if to else None
    try:
        report = _run(
            service.get_summary(
                organization_id=organization_id, project_id=project_id, from_date=from_date, to_date=to_date
            )
        )
    except TestPilotError as exc:
        _handle_error(exc, json_output)
        return

    if json_output:
        typer.echo(
            json.dumps(
                {
                    "total": report.total,
                    "passed": report.passed,
                    "failed": report.failed,
                    "skipped": report.skipped,
                    "pass_percentage": report.pass_percentage,
                    "failure_percentage": report.failure_percentage,
                    "coverage_percentage": report.coverage_percentage,
                }
            )
        )
        return

    typer.echo(f"Total: {report.total}")
    typer.echo(f"Passed: {report.passed}")
    typer.echo(f"Failed: {report.failed}")
    typer.echo(f"Skipped: {report.skipped}")
    typer.echo(f"Pass percentage: {report.pass_percentage:.1f}%")
    typer.echo(f"Failure percentage: {report.failure_percentage:.1f}%")
    typer.echo(f"Coverage percentage: {report.coverage_percentage:.1f}%")
