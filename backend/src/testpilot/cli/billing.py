"""testpilot-cli billing (constitution Principle II; quickstart.md Section 13).

Assembled into the top-level `testpilot-cli` entrypoint by cli/main.py
(T238, Phase 26) alongside every other domain's CLI app — this module owns
its own Typer app so it can be built and tested independently here, next
to the billing feature itself.
"""

import asyncio
import json
import uuid
from collections.abc import Coroutine
from typing import Any

import typer

from testpilot.billing import service
from testpilot.core.db import dispose_engine
from testpilot.core.redis import dispose_redis
from testpilot.orgs.models import SubscriptionTier

app = typer.Typer(help="Billing plan and usage administration.")


def _run[T](coro: Coroutine[Any, Any, T]) -> T:
    """Runs `coro` to completion and disposes the cached DB engine and
    Redis client before returning. Each CLI invocation is a fresh
    `asyncio.run()` call (a new event loop); connections created during
    this call must not be left cached for the next invocation's loop to
    (incorrectly) reuse (see core/db.py's engine caching and conftest.py's
    `_fresh_engine_per_test` docstring for the same underlying constraint
    — this is that same fix, applied where CLI invocations run outside
    pytest-asyncio's own per-test fixture).
    """

    async def _wrapped() -> T:
        try:
            return await coro
        finally:
            await dispose_engine()
            await dispose_redis()

    return asyncio.run(_wrapped())


def _limits_dict(plan: Any) -> dict[str, int | None]:
    return {
        "max_projects": plan.max_projects,
        "max_test_executions_per_period": plan.max_test_executions_per_period,
        "max_ai_operations_per_period": plan.max_ai_operations_per_period,
        "max_members": plan.max_members,
    }


@app.command("show")
def show(
    organization_id: uuid.UUID,
    json_output: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Show an Organization's current plan, limits, and this period's usage."""
    plan, usage = _run(service.get_billing_summary(organization_id=organization_id))

    if json_output:
        typer.echo(json.dumps({"tier": plan.tier.value, "limits": _limits_dict(plan), "usage": usage}))
        return

    typer.echo(f"Plan: {plan.tier.value}")
    for key, value in _limits_dict(plan).items():
        typer.echo(f"  {key}: {value}")
    typer.echo("Usage this period:")
    for metric, count in usage.items():
        typer.echo(f"  {metric}: {count}")


@app.command("set-plan")
def set_plan(
    organization_id: uuid.UUID,
    tier: SubscriptionTier,
    max_projects: int | None = typer.Option(None, "--max-projects"),
    max_test_executions: int | None = typer.Option(None, "--max-test-executions"),
    max_ai_operations: int | None = typer.Option(None, "--max-ai-operations"),
    max_members: int | None = typer.Option(None, "--max-members"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Assign an Organization to a plan tier, optionally overriding that
    tier's limits (admin/test tool — quickstart.md Section 13)."""
    organization, plan = _run(
        service.set_plan_for_organization(
            organization_id=organization_id,
            tier=tier,
            max_projects=max_projects,
            max_test_executions_per_period=max_test_executions,
            max_ai_operations_per_period=max_ai_operations,
            max_members=max_members,
        )
    )

    if json_output:
        typer.echo(
            json.dumps({"organization_id": str(organization.id), "tier": plan.tier.value, **_limits_dict(plan)})
        )
        return

    typer.echo(f"Organization {organization.id} set to plan '{plan.tier.value}'")
    for key, value in _limits_dict(plan).items():
        typer.echo(f"  {key}: {value}")
