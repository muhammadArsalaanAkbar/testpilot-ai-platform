"""CLI tests for testpilot-cli billing (constitution Principle II; quickstart.md Section 13)."""

import asyncio
import json
import uuid

from sqlalchemy import select
from typer.testing import CliRunner

from testpilot.auth.models import User
from testpilot.cli.billing import app
from testpilot.core.db import dispose_engine, session_scope, set_rls_context
from testpilot.core.redis import dispose_redis
from testpilot.orgs.models import (
    Membership,
    MembershipRole,
    Organization,
    SubscriptionPlan,
    SubscriptionTier,
)

runner = CliRunner()


def _run(coro):  # type: ignore[no-untyped-def]
    """Each top-level asyncio.run() call (one per CLI invocation, matching
    real CLI-process usage) needs its own disposal of the cached engine
    before returning — asyncpg connections are bound to the loop that
    created them, and the next asyncio.run() call opens a new loop (see
    conftest.py's _fresh_engine_per_test docstring for the same root cause
    across tests; this is the same issue, but across sequential
    within-test asyncio.run() calls instead)."""

    async def _wrapped():  # type: ignore[no-untyped-def]
        try:
            return await coro
        finally:
            await dispose_engine()
            await dispose_redis()

    return asyncio.run(_wrapped())


async def _create_organization(*, tier: SubscriptionTier = SubscriptionTier.free) -> uuid.UUID:
    async with session_scope() as session:
        plan_result = await session.execute(select(SubscriptionPlan).where(SubscriptionPlan.tier == tier))
        plan = plan_result.scalar_one()

        user = User(email=f"{uuid.uuid4()}@example.com", name="CLI Test User", password_hash="x")
        session.add(user)
        await session.flush()

        organization = Organization(name="CLI Test Org", slug=str(uuid.uuid4()), plan_id=plan.id)
        session.add(organization)
        await session.flush()

        await set_rls_context(session, organization_id=str(organization.id), user_id=str(user.id))
        session.add(Membership(organization_id=organization.id, user_id=user.id, role=MembershipRole.owner))
        await session.flush()
        return organization.id


def test_show_reports_free_plan_and_zero_usage() -> None:
    organization_id = _run(_create_organization())

    result = runner.invoke(app, ["show", str(organization_id), "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["tier"] == "free"
    assert payload["usage"]["projects"] == 0


async def _read_free_plan_max_projects() -> int | None:
    async with session_scope() as session:
        result = await session.execute(
            select(SubscriptionPlan.max_projects).where(SubscriptionPlan.tier == SubscriptionTier.free)
        )
        return result.scalar_one()


async def _write_free_plan_max_projects(value: int | None) -> None:
    async with session_scope() as session:
        plan_result = await session.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.tier == SubscriptionTier.free)
        )
        plan = plan_result.scalar_one()
        plan.max_projects = value
        session.add(plan)


def test_set_plan_overrides_limits_and_reassigns_tier() -> None:
    """`subscription_plans` is shared catalog data (one row per tier, not per
    Organization) — the override this test exercises mutates that row for
    every Organization on the tier, so the original value is restored on
    teardown to avoid leaking state into other tests/phases that assume the
    seeded default (alembic/versions/c828fd4bd7d5_seed_subscription_plan_tiers.py)."""
    original_max_projects = _run(_read_free_plan_max_projects())
    try:
        organization_id = _run(_create_organization())

        result = runner.invoke(app, ["set-plan", str(organization_id), "free", "--max-projects", "7", "--json"])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["tier"] == "free"
        assert payload["max_projects"] == 7

        show_result = runner.invoke(app, ["show", str(organization_id), "--json"])
        show_payload = json.loads(show_result.output)
        assert show_payload["limits"]["max_projects"] == 7
    finally:
        _run(_write_free_plan_max_projects(original_max_projects))
