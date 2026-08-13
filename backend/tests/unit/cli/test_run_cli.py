"""CLI tests for testpilot-cli run execute/list/retry-failed (T250,
constitution Principle II). Wraps the `execution` library directly (not the
HTTP API), same pattern as test_ai_generate_cli.py/test_billing_cli.py.
"""

import asyncio
import json
import uuid

import pytest
from sqlalchemy import select
from typer.testing import CliRunner

from testpilot.auth.models import User
from testpilot.cli.run import app
from testpilot.core.db import dispose_engine, session_scope, set_rls_context
from testpilot.core.redis import dispose_redis
from testpilot.execution import runner as execution_runner
from testpilot.execution.playwright_engine import PlaywrightEngine
from testpilot.orgs.models import (
    Membership,
    MembershipRole,
    Organization,
    SubscriptionPlan,
    SubscriptionTier,
)
from testpilot.projects import service as projects_service
from testpilot.projects.models import Project
from testpilot.testcases import service as testcases_service
from testpilot.testcases.models import TestCasePriority, TestCaseSeverity, TestStepActionType
from testpilot.testcases.service import StepInput

runner = CliRunner()


async def _public_resolver(hostname: str) -> list[str]:
    return ["8.8.8.8"]


def _run(coro):  # type: ignore[no-untyped-def]
    async def _wrapped():  # type: ignore[no-untyped-def]
        try:
            return await coro
        finally:
            await dispose_engine()
            await dispose_redis()

    return asyncio.run(_wrapped())


async def _create_org_user_project_and_approved_case(fixture_site_url: str) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
    async with session_scope() as session:
        plan_result = await session.execute(select(SubscriptionPlan).where(SubscriptionPlan.tier == SubscriptionTier.free))
        plan = plan_result.scalar_one()

        user = User(email=f"{uuid.uuid4()}@example.com", name="CLI Run Test User", password_hash="x")
        session.add(user)
        await session.flush()

        organization = Organization(name="CLI Run Test Org", slug=str(uuid.uuid4()), plan_id=plan.id)
        session.add(organization)
        await session.flush()

        await set_rls_context(session, organization_id=str(organization.id), user_id=str(user.id))
        session.add(Membership(organization_id=organization.id, user_id=user.id, role=MembershipRole.owner))
        await session.flush()
        organization_id, user_id = organization.id, user.id

    project = await projects_service.create_project(
        organization_id=organization_id, name="CLI Run Project", url="https://example.com"
    )

    async with session_scope(organization_id=str(organization_id)) as session:
        result = await session.execute(select(Project).where(Project.id == project.id))
        project_row = result.scalar_one()
        project_row.url = fixture_site_url
        session.add(project_row)

    test_case, _steps = await testcases_service.create_test_case(
        organization_id=organization_id,
        project_id=project.id,
        title="CLI case",
        description="D",
        priority=TestCasePriority.low,
        severity=TestCaseSeverity.minor,
        steps=[StepInput(action_type=TestStepActionType.navigate, target_descriptor=fixture_site_url)],
    )
    await testcases_service.approve_test_case(
        organization_id=organization_id, project_id=project.id, test_case_id=test_case.id
    )
    return organization_id, user_id, project.id, test_case.id


def test_run_execute_enqueues_a_queued_run(fixture_site_url) -> None:
    organization_id, user_id, project_id, test_case_id = _run(
        _create_org_user_project_and_approved_case(fixture_site_url)
    )

    result = runner.invoke(
        app, ["execute", str(organization_id), str(project_id), str(user_id), str(test_case_id), "--json"]
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "queued"
    assert payload["project_id"] == str(project_id)
    assert payload["summary_total"] == 1
    assert payload["id"]


def test_run_execute_human_readable_output(fixture_site_url) -> None:
    organization_id, user_id, project_id, test_case_id = _run(
        _create_org_user_project_and_approved_case(fixture_site_url)
    )

    result = runner.invoke(app, ["execute", str(organization_id), str(project_id), str(user_id), str(test_case_id)])

    assert result.exit_code == 0, result.output
    assert "queued" in result.output.lower()
    with pytest.raises(json.JSONDecodeError):
        json.loads(result.output)


def test_run_execute_then_processed_completes_with_real_results(fixture_site_url) -> None:
    """T251: the enqueued run, once processed (simulating the worker) with
    the real PlaywrightEngine against the local fixture site, completes with
    a genuine pass — not a mocked success."""
    organization_id, user_id, project_id, test_case_id = _run(
        _create_org_user_project_and_approved_case(fixture_site_url)
    )

    result = runner.invoke(
        app, ["execute", str(organization_id), str(project_id), str(user_id), str(test_case_id), "--json"]
    )
    run_id = json.loads(result.output)["id"]

    async def _process() -> None:
        engine = PlaywrightEngine(url_resolver=_public_resolver)
        try:
            await execution_runner.run_test_run(
                test_run_id=uuid.UUID(run_id), organization_id=organization_id, engine=engine
            )
        finally:
            await engine.close()

    _run(_process())

    list_result = runner.invoke(app, ["list", str(organization_id), str(project_id), "--json"])
    runs = json.loads(list_result.output)["items"]
    completed = next(r for r in runs if r["id"] == run_id)
    assert completed["status"] == "completed"
    assert completed["summary_passed"] == 1


def test_run_list_human_readable_output(fixture_site_url) -> None:
    organization_id, user_id, project_id, test_case_id = _run(
        _create_org_user_project_and_approved_case(fixture_site_url)
    )
    runner.invoke(app, ["execute", str(organization_id), str(project_id), str(user_id), str(test_case_id), "--json"])

    result = runner.invoke(app, ["list", str(organization_id), str(project_id)])

    assert result.exit_code == 0, result.output
    assert "queued" in result.output.lower()


def test_run_retry_failed_on_non_terminal_run_reports_conflict_error(fixture_site_url) -> None:
    organization_id, user_id, project_id, test_case_id = _run(
        _create_org_user_project_and_approved_case(fixture_site_url)
    )
    create = runner.invoke(
        app, ["execute", str(organization_id), str(project_id), str(user_id), str(test_case_id), "--json"]
    )
    run_id = json.loads(create.output)["id"]

    result = runner.invoke(app, ["retry-failed", str(organization_id), str(project_id), run_id, str(user_id), "--json"])

    assert result.exit_code != 0
    assert "run_not_completed" in result.output


def test_run_retry_failed_after_completion_scopes_to_failed_cases(fixture_site_url) -> None:
    organization_id, user_id, project_id, test_case_id = _run(
        _create_org_user_project_and_approved_case(fixture_site_url)
    )
    create = runner.invoke(
        app, ["execute", str(organization_id), str(project_id), str(user_id), str(test_case_id), "--json"]
    )
    run_id = json.loads(create.output)["id"]

    async def _process() -> None:
        engine = PlaywrightEngine(url_resolver=_public_resolver)
        try:
            await execution_runner.run_test_run(
                test_run_id=uuid.UUID(run_id), organization_id=organization_id, engine=engine
            )
        finally:
            await engine.close()

    _run(_process())

    result = runner.invoke(app, ["retry-failed", str(organization_id), str(project_id), run_id, str(user_id), "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    # The one case passed, so retry-failed has nothing to retry.
    assert payload["summary_total"] == 0
