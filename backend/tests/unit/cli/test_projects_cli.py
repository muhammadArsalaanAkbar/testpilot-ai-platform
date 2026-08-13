"""CLI tests for testpilot-cli projects (constitution Principle II, T244)."""

import asyncio
import json
import uuid

from sqlalchemy import select
from typer.testing import CliRunner

from testpilot.auth.models import User
from testpilot.cli.projects import app
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
    """See test_billing_cli.py's `_run` for why disposal is required after
    every top-level asyncio.run() call in these tests."""

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


def test_create_then_list_shows_the_new_project() -> None:
    organization_id = _run(_create_organization())

    create_result = runner.invoke(
        app, ["create", str(organization_id), "CLI Project", "https://example.com", "--json"]
    )
    assert create_result.exit_code == 0, create_result.output
    created = json.loads(create_result.output)
    assert created["name"] == "CLI Project"
    assert created["status"] == "active"

    list_result = runner.invoke(app, ["list", str(organization_id), "--json"])
    assert list_result.exit_code == 0, list_result.output
    items = json.loads(list_result.output)["items"]
    assert any(p["id"] == created["id"] for p in items)


def test_create_rejects_a_private_ip_url() -> None:
    organization_id = _run(_create_organization())

    result = runner.invoke(app, ["create", str(organization_id), "Bad", "http://127.0.0.1/", "--json"])

    assert result.exit_code != 0
    assert "url_not_public" in result.output


def test_archive_marks_the_project_archived_and_filters_list() -> None:
    organization_id = _run(_create_organization())

    create_result = runner.invoke(
        app, ["create", str(organization_id), "Archive Me", "https://example.com", "--json"]
    )
    project_id = json.loads(create_result.output)["id"]

    archive_result = runner.invoke(app, ["archive", str(organization_id), project_id, "--json"])
    assert archive_result.exit_code == 0, archive_result.output
    assert json.loads(archive_result.output)["status"] == "archived"

    active_list = runner.invoke(app, ["list", str(organization_id), "--status", "active", "--json"])
    assert not any(p["id"] == project_id for p in json.loads(active_list.output)["items"])

    archived_list = runner.invoke(app, ["list", str(organization_id), "--status", "archived", "--json"])
    assert any(p["id"] == project_id for p in json.loads(archived_list.output)["items"])
