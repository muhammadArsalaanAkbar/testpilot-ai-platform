"""CLI tests for testpilot-cli ai analyze (T252, constitution Principle II)."""

import asyncio
import json
import uuid

from sqlalchemy import select
from typer.testing import CliRunner

from testpilot.ai_analysis import service as ai_analysis_service
from testpilot.ai_analysis.models import AIAnalysisStatus
from testpilot.ai_provider.fake import FakeLLMProvider
from testpilot.auth.models import User
from testpilot.cli.ai import app
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


async def _create_org_user_and_failed_result(fixture_site_url: str) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
    async with session_scope() as session:
        plan_result = await session.execute(select(SubscriptionPlan).where(SubscriptionPlan.tier == SubscriptionTier.free))
        plan = plan_result.scalar_one()

        user = User(email=f"{uuid.uuid4()}@example.com", name="CLI Analyze Test User", password_hash="x")
        session.add(user)
        await session.flush()

        organization = Organization(name="CLI Analyze Test Org", slug=str(uuid.uuid4()), plan_id=plan.id)
        session.add(organization)
        await session.flush()

        await set_rls_context(session, organization_id=str(organization.id), user_id=str(user.id))
        session.add(Membership(organization_id=organization.id, user_id=user.id, role=MembershipRole.owner))
        await session.flush()
        organization_id, user_id = organization.id, user.id

    project = await projects_service.create_project(
        organization_id=organization_id, name="CLI Analyze Project", url="https://example.com"
    )
    async with session_scope(organization_id=str(organization_id)) as session:
        result = await session.execute(select(Project).where(Project.id == project.id))
        project_row = result.scalar_one()
        project_row.url = fixture_site_url
        session.add(project_row)

    test_case, _steps = await testcases_service.create_test_case(
        organization_id=organization_id,
        project_id=project.id,
        title="Failing case",
        description="D",
        priority=TestCasePriority.low,
        severity=TestCaseSeverity.minor,
        steps=[
            StepInput(action_type=TestStepActionType.navigate, target_descriptor=fixture_site_url),
            StepInput(
                action_type=TestStepActionType.assert_element,
                target_descriptor="#does-not-exist",
                expected_assertion="present",
            ),
        ],
    )
    await testcases_service.approve_test_case(
        organization_id=organization_id, project_id=project.id, test_case_id=test_case.id
    )

    from testpilot.execution import service as execution_service

    test_run = await execution_service.create_test_run(
        organization_id=organization_id, project_id=project.id, initiated_by_user_id=user_id,
        test_case_ids=[test_case.id],
    )
    engine = PlaywrightEngine(url_resolver=_public_resolver)
    try:
        await execution_runner.run_test_run(test_run_id=test_run.id, organization_id=organization_id, engine=engine)
    finally:
        await engine.close()

    _run_detail, results = await execution_service.get_test_run(
        organization_id=organization_id, project_id=project.id, test_run_id=test_run.id
    )
    return organization_id, user_id, project.id, test_run.id, results[0].id


def test_analyze_enqueues_a_queued_analysis(fixture_site_url) -> None:
    organization_id, user_id, project_id, test_run_id, test_result_id = _run(
        _create_org_user_and_failed_result(fixture_site_url)
    )

    result = runner.invoke(
        app,
        [
            "analyze",
            str(organization_id),
            str(project_id),
            str(test_run_id),
            str(test_result_id),
            str(user_id),
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "queued"
    assert payload["test_result_id"] == str(test_result_id)
    assert payload["id"]


def test_analyze_human_readable_output(fixture_site_url) -> None:
    organization_id, user_id, project_id, test_run_id, test_result_id = _run(
        _create_org_user_and_failed_result(fixture_site_url)
    )

    result = runner.invoke(
        app, ["analyze", str(organization_id), str(project_id), str(test_run_id), str(test_result_id), str(user_id)]
    )

    assert result.exit_code == 0, result.output
    assert "queued" in result.output.lower()


def test_analyze_then_processed_completes_with_a_real_analysis(fixture_site_url) -> None:
    organization_id, user_id, project_id, test_run_id, test_result_id = _run(
        _create_org_user_and_failed_result(fixture_site_url)
    )

    result = runner.invoke(
        app,
        [
            "analyze",
            str(organization_id),
            str(project_id),
            str(test_run_id),
            str(test_result_id),
            str(user_id),
            "--json",
        ],
    )
    analysis_id = uuid.UUID(json.loads(result.output)["id"])

    _run(
        ai_analysis_service.run_analysis(
            ai_analysis_id=analysis_id,
            organization_id=organization_id,
            test_result_id=test_result_id,
            provider=FakeLLMProvider(),
            storage=None,
        )
    )

    analysis = _run(
        ai_analysis_service.get_ai_analysis(
            organization_id=organization_id, project_id=project_id, test_run_id=test_run_id,
            test_result_id=test_result_id, analysis_id=analysis_id,
        )
    )
    assert analysis.status == AIAnalysisStatus.completed
    assert analysis.explanation


def test_analyze_a_passed_result_reports_conflict_error(fixture_site_url) -> None:
    organization_id, user_id, project_id, test_run_id, test_result_id = _run(
        _create_org_user_and_failed_result(fixture_site_url)
    )
    # Force the seeded result to "passed" directly, to exercise the
    # result_not_failed error path without a second full execution.
    from testpilot.execution.models import TestResult, TestResultStatus

    async def _mark_passed() -> None:
        async with session_scope(organization_id=str(organization_id)) as session:
            result = await session.execute(select(TestResult).where(TestResult.id == test_result_id))
            row = result.scalar_one()
            row.status = TestResultStatus.passed
            session.add(row)

    _run(_mark_passed())

    result = runner.invoke(
        app,
        [
            "analyze",
            str(organization_id),
            str(project_id),
            str(test_run_id),
            str(test_result_id),
            str(user_id),
            "--json",
        ],
    )

    assert result.exit_code != 0
    assert "result_not_failed" in result.output
