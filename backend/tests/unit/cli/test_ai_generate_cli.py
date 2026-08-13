"""CLI tests for testpilot-cli ai generate-tests (constitution Principle II, T248)."""

import asyncio
import json
import uuid

from sqlalchemy import select
from typer.testing import CliRunner

from testpilot.ai_generation import service as ai_generation_service
from testpilot.ai_generation.models import GenerationStatus
from testpilot.ai_provider.base import FormFieldSnapshot, FormSnapshot
from testpilot.ai_provider.fake import FakeLLMProvider
from testpilot.auth.models import User
from testpilot.cli.ai import app
from testpilot.core.db import dispose_engine, session_scope, set_rls_context
from testpilot.core.redis import dispose_redis
from testpilot.execution.engine import LoadedPage
from testpilot.orgs.models import (
    Membership,
    MembershipRole,
    Organization,
    SubscriptionPlan,
    SubscriptionTier,
)
from testpilot.projects import service as projects_service

runner = CliRunner()

# cli/ai.py now has two commands (`generate-tests`, `analyze` — T253 added
# the second), so Typer requires the subcommand name on every invocation
# (it only collapses to a single-command CLI, no name needed, for a
# Typer() app with exactly one @app.command()).


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


async def _create_organization_user_and_project() -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    async with session_scope() as session:
        plan_result = await session.execute(select(SubscriptionPlan).where(SubscriptionPlan.tier == SubscriptionTier.free))
        plan = plan_result.scalar_one()

        user = User(email=f"{uuid.uuid4()}@example.com", name="CLI AI Test User", password_hash="x")
        session.add(user)
        await session.flush()

        organization = Organization(name="CLI AI Test Org", slug=str(uuid.uuid4()), plan_id=plan.id)
        session.add(organization)
        await session.flush()

        await set_rls_context(session, organization_id=str(organization.id), user_id=str(user.id))
        session.add(Membership(organization_id=organization.id, user_id=user.id, role=MembershipRole.owner))
        await session.flush()
        organization_id, user_id = organization.id, user.id

    project = await projects_service.create_project(
        organization_id=organization_id, name="CLI AI Project", url="https://example.com"
    )
    return organization_id, user_id, project.id


class _FakeEngineWithForm:
    async def load_page(self, url: str) -> LoadedPage:
        return LoadedPage(
            url=url,
            title="Sign Up",
            headings=["Create your account"],
            forms=[
                FormSnapshot(
                    action="/signup",
                    method="post",
                    fields=[FormFieldSnapshot(name="email", field_type="email")],
                )
            ],
            interactive_elements=[],
            links=[],
        )


def test_generate_tests_enqueues_a_queued_run() -> None:
    organization_id, user_id, project_id = _run(_create_organization_user_and_project())

    result = runner.invoke(
        app, ["generate-tests", str(organization_id), str(project_id), str(user_id), "--json"]
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "queued"
    assert payload["scope"] == "full_batch"
    assert payload["id"]


def test_generate_tests_run_completes_with_the_fake_provider() -> None:
    """T248: the enqueued run, once processed (simulating the worker) with
    the fake LLMProvider adapter, completes with real generated content."""
    organization_id, user_id, project_id = _run(_create_organization_user_and_project())

    result = runner.invoke(
        app, ["generate-tests", str(organization_id), str(project_id), str(user_id), "--json"]
    )
    run_id = uuid.UUID(json.loads(result.output)["id"])

    _run(
        ai_generation_service.run_generation(
            generation_run_id=run_id,
            organization_id=organization_id,
            provider=FakeLLMProvider(),
            engine=_FakeEngineWithForm(),
        )
    )

    completed_run = _run(
        ai_generation_service.get_generation_run(
            organization_id=organization_id, project_id=project_id, generation_run_id=run_id
        )
    )
    assert completed_run.status == GenerationStatus.completed
    assert len(completed_run.created_test_case_ids) > 0


def test_generate_tests_twice_reports_conflict_error() -> None:
    organization_id, user_id, project_id = _run(_create_organization_user_and_project())

    first = runner.invoke(app, ["generate-tests", str(organization_id), str(project_id), str(user_id), "--json"])
    assert first.exit_code == 0, first.output

    second = runner.invoke(app, ["generate-tests", str(organization_id), str(project_id), str(user_id), "--json"])
    assert second.exit_code != 0
    assert "generation_in_progress" in second.output
