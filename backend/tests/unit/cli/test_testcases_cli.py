"""CLI tests for testpilot-cli testcases (constitution Principle II, T246)."""

import asyncio
import json
import uuid

from sqlalchemy import select
from typer.testing import CliRunner

from testpilot.auth.models import User
from testpilot.cli.testcases import app
from testpilot.core.db import dispose_engine, session_scope, set_rls_context
from testpilot.core.redis import dispose_redis
from testpilot.orgs.models import (
    Membership,
    MembershipRole,
    Organization,
    SubscriptionPlan,
    SubscriptionTier,
)
from testpilot.projects import service as projects_service

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


async def _create_organization_and_project() -> tuple[uuid.UUID, uuid.UUID]:
    organization_id = await _create_organization()
    project = await projects_service.create_project(
        organization_id=organization_id, name="CLI TC Project", url="https://example.com"
    )
    return organization_id, project.id


def test_create_then_list_shows_the_new_test_case() -> None:
    organization_id, project_id = _run(_create_organization_and_project())

    create_result = runner.invoke(
        app,
        [
            "create",
            str(organization_id),
            str(project_id),
            "Login works",
            "Verify login succeeds with valid credentials.",
            "--priority",
            "high",
            "--severity",
            "major",
            "--json",
        ],
    )
    assert create_result.exit_code == 0, create_result.output
    created = json.loads(create_result.output)
    assert created["title"] == "Login works"
    assert created["status"] == "draft"
    assert created["source"] == "manual"

    list_result = runner.invoke(app, ["list", str(organization_id), str(project_id), "--json"])
    assert list_result.exit_code == 0, list_result.output
    items = json.loads(list_result.output)["items"]
    assert any(c["id"] == created["id"] for c in items)


def test_approve_then_reject_transitions() -> None:
    organization_id, project_id = _run(_create_organization_and_project())

    create_result = runner.invoke(
        app,
        [
            "create",
            str(organization_id),
            str(project_id),
            "Case",
            "Description.",
            "--priority",
            "low",
            "--severity",
            "minor",
            "--json",
        ],
    )
    test_case_id = json.loads(create_result.output)["id"]

    approve_result = runner.invoke(app, ["approve", str(organization_id), str(project_id), test_case_id, "--json"])
    assert approve_result.exit_code == 0, approve_result.output
    assert json.loads(approve_result.output)["status"] == "approved"

    reject_result = runner.invoke(app, ["reject", str(organization_id), str(project_id), test_case_id, "--json"])
    assert reject_result.exit_code == 0, reject_result.output
    assert json.loads(reject_result.output)["status"] == "rejected"


def test_list_filters_by_status() -> None:
    organization_id, project_id = _run(_create_organization_and_project())

    create_result = runner.invoke(
        app,
        [
            "create",
            str(organization_id),
            str(project_id),
            "Filterable",
            "Description.",
            "--priority",
            "low",
            "--severity",
            "minor",
            "--json",
        ],
    )
    test_case_id = json.loads(create_result.output)["id"]
    runner.invoke(app, ["approve", str(organization_id), str(project_id), test_case_id, "--json"])

    draft_list = runner.invoke(app, ["list", str(organization_id), str(project_id), "--status", "draft", "--json"])
    assert not any(c["id"] == test_case_id for c in json.loads(draft_list.output)["items"])

    approved_list = runner.invoke(
        app, ["list", str(organization_id), str(project_id), "--status", "approved", "--json"]
    )
    assert any(c["id"] == test_case_id for c in json.loads(approved_list.output)["items"])
