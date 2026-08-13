"""testpilot-cli projects (constitution Principle II, T245).

Wraps the `projects` library directly (not the HTTP API) — see cli/billing.py
for the pattern this follows, including the per-invocation engine-disposal
requirement explained in its `_run` docstring.
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
from testpilot.projects import service
from testpilot.projects.models import Project, ProjectStatus

app = typer.Typer(help="Project administration.")


def _run[T](coro: Coroutine[Any, Any, T]) -> T:
    async def _wrapped() -> T:
        try:
            return await coro
        finally:
            await dispose_engine()
            await dispose_redis()

    return asyncio.run(_wrapped())


def _to_dict(project: Project) -> dict[str, Any]:
    return {
        "id": str(project.id),
        "name": project.name,
        "url": project.url,
        "status": project.status.value,
        "settings": project.settings,
    }


@app.command("list")
def list_projects(
    organization_id: uuid.UUID,
    status_filter: ProjectStatus | None = typer.Option(None, "--status"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """List an Organization's projects, optionally filtered by status."""
    projects = _run(service.list_projects(organization_id=organization_id, status=status_filter))

    if json_output:
        typer.echo(json.dumps({"items": [_to_dict(p) for p in projects]}))
        return

    for project in projects:
        typer.echo(f"{project.id}  {project.status.value:8}  {project.name}  {project.url}")


@app.command("create")
def create_project(
    organization_id: uuid.UUID,
    name: str,
    url: str,
    json_output: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Create a project, subject to the same SSRF guard and plan-limit
    enforcement as the HTTP API."""
    try:
        project = _run(service.create_project(organization_id=organization_id, name=name, url=url))
    except TestPilotError as exc:
        if json_output:
            typer.echo(json.dumps({"error": {"code": exc.code, "message": exc.message}}))
        else:
            typer.echo(f"Error [{exc.code}]: {exc.message}")
        raise typer.Exit(code=1) from None

    if json_output:
        typer.echo(json.dumps(_to_dict(project)))
        return
    typer.echo(f"Created project {project.id}  {project.name}  {project.url}")


@app.command("archive")
def archive_project(
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
    json_output: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Archive a project (idempotent)."""
    try:
        project = _run(service.archive_project(organization_id=organization_id, project_id=project_id))
    except TestPilotError as exc:
        if json_output:
            typer.echo(json.dumps({"error": {"code": exc.code, "message": exc.message}}))
        else:
            typer.echo(f"Error [{exc.code}]: {exc.message}")
        raise typer.Exit(code=1) from None

    if json_output:
        typer.echo(json.dumps(_to_dict(project)))
        return
    typer.echo(f"Archived project {project.id}")
