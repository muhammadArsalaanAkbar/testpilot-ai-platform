"""CLI tests for testpilot-cli reports (T254, constitution Principle II)."""

import asyncio
import json
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from typer.testing import CliRunner

from testpilot.auth.models import User
from testpilot.cli.reports import app
from testpilot.core.db import dispose_engine, session_scope, set_rls_context
from testpilot.core.redis import dispose_redis
from testpilot.execution.models import TestResult, TestResultStatus, TestRun
from testpilot.orgs.models import (
    Membership,
    MembershipRole,
    Organization,
    SubscriptionPlan,
    SubscriptionTier,
)
from testpilot.projects.models import Project
from testpilot.testcases.models import (
    TestCase,
    TestCasePriority,
    TestCaseSeverity,
    TestCaseSource,
    TestCaseStatus,
)

runner = CliRunner()


def _run(coro):  # type: ignore[no-untyped-def]
    async def _wrapped():  # type: ignore[no-untyped-def]
        try:
            return await coro
        finally:
            await dispose_engine()
            await dispose_redis()

    return asyncio.run(_wrapped())


async def _seed() -> tuple[uuid.UUID, uuid.UUID]:
    async with session_scope() as session:
        plan_result = await session.execute(select(SubscriptionPlan).where(SubscriptionPlan.tier == SubscriptionTier.free))
        plan = plan_result.scalar_one()

        user = User(email=f"{uuid.uuid4()}@example.com", name="CLI Reports User", password_hash="x")
        session.add(user)
        await session.flush()

        organization = Organization(name="CLI Reports Org", slug=str(uuid.uuid4()), plan_id=plan.id)
        session.add(organization)
        await session.flush()

        await set_rls_context(session, organization_id=str(organization.id), user_id=str(user.id))
        session.add(Membership(organization_id=organization.id, user_id=user.id, role=MembershipRole.owner))

        project = Project(organization_id=organization.id, name="CLI Reports Project", url="https://example.com")
        session.add(project)
        await session.flush()

        case = TestCase(
            organization_id=organization.id,
            project_id=project.id,
            title="Case",
            description="A test case.",
            priority=TestCasePriority.medium,
            severity=TestCaseSeverity.major,
            status=TestCaseStatus.approved,
            source=TestCaseSource.manual,
        )
        session.add(case)
        await session.flush()

        now = datetime.now(UTC)
        run = TestRun(
            organization_id=organization.id,
            project_id=project.id,
            initiated_by_user_id=user.id,
            summary_total=1,
            summary_passed=1,
            summary_failed=0,
            summary_skipped=0,
            created_at=now,
        )
        session.add(run)
        await session.flush()
        session.add(
            TestResult(
                organization_id=organization.id,
                test_run_id=run.id,
                test_case_id=case.id,
                status=TestResultStatus.passed,
                started_at=now,
                completed_at=now,
                duration_ms=100,
            )
        )
        await session.flush()

        return organization.id, project.id


def test_summary_json_output_matches_seeded_data() -> None:
    organization_id, project_id = _run(_seed())

    result = runner.invoke(app, ["summary", str(organization_id), str(project_id), "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["total"] == 1
    assert payload["passed"] == 1
    assert payload["failed"] == 0
    assert payload["pass_percentage"] == 100.0
    assert payload["coverage_percentage"] == 100.0


def test_summary_human_readable_output_shows_key_figures() -> None:
    organization_id, project_id = _run(_seed())

    result = runner.invoke(app, ["summary", str(organization_id), str(project_id)])

    assert result.exit_code == 0, result.output
    assert "total: 1" in result.output.lower() or "Total: 1" in result.output
    assert "pass" in result.output.lower()


def test_summary_errors_cleanly_for_a_nonexistent_project() -> None:
    organization_id, _project_id = _run(_seed())

    result = runner.invoke(app, ["summary", str(organization_id), str(uuid.uuid4()), "--json"])

    assert result.exit_code != 0
    payload = json.loads(result.output)
    assert payload["error"]["code"] == "not_found"
