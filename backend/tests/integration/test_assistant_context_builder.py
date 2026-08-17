"""Integration tests for assistant/context_builder.py's bounds/limits and
secret-exclusion guarantees (assistant spec: "bounded context builder...
never dump the entire database/project into every request" and "never send
sensitive infrastructure secrets to the model").
"""

import json
import uuid

import pytest

from testpilot.assistant import context_builder
from testpilot.core.db import session_scope
from testpilot.issues.models import Issue, IssuePriority, IssueSeverity
from testpilot.projects.models import Project
from testpilot.testcases import service as testcases_service
from testpilot.testcases.models import TestCasePriority, TestCaseSeverity
from testpilot.testcases.service import StepInput

pytestmark = pytest.mark.anyio


async def _signup_and_get_token(client, email="assistant-context@example.com"):
    r = await client.post(
        "/auth/signup", json={"email": email, "password": "correct horse battery staple", "name": "Context Test"}
    )
    body = r.json()
    return body["access_token"], body["organization"]["id"]


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _create_project(client, token, name="Context Project", settings: dict | None = None):
    payload = {"name": name, "url": "https://example.com"}
    if settings is not None:
        payload["settings"] = settings
    r = await client.post("/projects", json=payload, headers=_auth_headers(token))
    return r.json()["id"]


async def _make_test_case(*, organization_id: str, project_id: str, title: str, steps: list[StepInput] | None = None):
    await testcases_service.create_test_case(
        organization_id=uuid.UUID(organization_id),
        project_id=uuid.UUID(project_id),
        title=title,
        description="A test case.",
        priority=TestCasePriority.medium,
        severity=TestCaseSeverity.major,
        steps=steps,
    )


async def _make_issue(*, organization_id: str, project_id: str, user_id: str, title: str) -> None:
    async with session_scope(organization_id=organization_id) as session:
        session.add(
            Issue(
                organization_id=uuid.UUID(organization_id),
                project_id=uuid.UUID(project_id),
                title=title,
                description="An issue.",
                severity=IssueSeverity.major,
                priority=IssuePriority.medium,
                created_by_user_id=uuid.UUID(user_id),
            )
        )


async def test_context_is_none_for_a_nonexistent_project(client):
    token, organization_id = await _signup_and_get_token(client)

    async with session_scope(organization_id=organization_id) as session:
        context = await context_builder.build_project_context(
            session, organization_id=uuid.UUID(organization_id), project_id=uuid.uuid4()
        )

    assert context is None


async def test_test_cases_are_capped_at_the_documented_limit(client):
    token, organization_id = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)

    for i in range(context_builder.MAX_TEST_CASES + 5):
        await _make_test_case(organization_id=organization_id, project_id=project_id, title=f"Case {i}")

    async with session_scope(organization_id=organization_id) as session:
        context = await context_builder.build_project_context(
            session, organization_id=uuid.UUID(organization_id), project_id=uuid.UUID(project_id)
        )

    assert context is not None
    assert len(context["test_cases"]) == context_builder.MAX_TEST_CASES


async def test_test_steps_are_capped_per_case(client):
    token, organization_id = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)
    many_steps = [
        StepInput(action_type="click", target_descriptor=f"#el-{i}")
        for i in range(context_builder.MAX_TEST_STEPS_PER_CASE + 5)
    ]

    await _make_test_case(organization_id=organization_id, project_id=project_id, title="Case with many steps", steps=many_steps)

    async with session_scope(organization_id=organization_id) as session:
        context = await context_builder.build_project_context(
            session, organization_id=uuid.UUID(organization_id), project_id=uuid.UUID(project_id)
        )

    assert context is not None
    assert len(context["test_cases"][0]["steps"]) == context_builder.MAX_TEST_STEPS_PER_CASE


async def test_issues_are_capped_at_the_documented_limit(client):
    token, organization_id = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)
    body = (await client.get("/auth/me", headers=_auth_headers(token))).json()
    user_id = body["user"]["id"]

    for i in range(context_builder.MAX_ISSUES + 5):
        await _make_issue(organization_id=organization_id, project_id=project_id, user_id=user_id, title=f"Issue {i}")

    async with session_scope(organization_id=organization_id) as session:
        context = await context_builder.build_project_context(
            session, organization_id=uuid.UUID(organization_id), project_id=uuid.UUID(project_id)
        )

    assert context is not None
    assert len(context["issues"]) == context_builder.MAX_ISSUES


async def test_long_text_fields_are_truncated(client):
    token, organization_id = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)
    long_description = "A" * (context_builder.MAX_TEXT_FIELD_CHARS + 500)

    await testcases_service.create_test_case(
        organization_id=uuid.UUID(organization_id),
        project_id=uuid.UUID(project_id),
        title="Long case",
        description=long_description,
        priority=TestCasePriority.medium,
        severity=TestCaseSeverity.major,
    )

    async with session_scope(organization_id=organization_id) as session:
        context = await context_builder.build_project_context(
            session, organization_id=uuid.UUID(organization_id), project_id=uuid.UUID(project_id)
        )

    assert context is not None
    described = context["test_cases"][0]["description"]
    assert len(described) < len(long_description)
    assert described.endswith("…[truncated]")


async def test_project_settings_never_appear_in_the_built_context(client):
    """Project.settings is free-form JSONB an operator could put arbitrary
    config (including test-site credentials) into — context_builder.py must
    never surface it, regardless of what it contains."""
    token, organization_id = await _signup_and_get_token(client)
    project_id = await _create_project(
        client, token, settings={"login_password": "s3cr3t-value", "api_key": "sk-should-never-leak"}
    )

    async with session_scope(organization_id=organization_id) as session:
        context = await context_builder.build_project_context(
            session, organization_id=uuid.UUID(organization_id), project_id=uuid.UUID(project_id)
        )

    assert context is not None
    assert "settings" not in context["project"]
    serialized = json.dumps(context)
    assert "s3cr3t-value" not in serialized
    assert "sk-should-never-leak" not in serialized


async def test_context_is_scoped_to_the_requested_project_only(client):
    """A second project's test cases/issues in the same Organization must
    never leak into the first project's context."""
    token, organization_id = await _signup_and_get_token(client)
    project_a = await _create_project(client, token, name="Project A")
    # Created directly (not via POST /projects) since the default plan caps
    # an Organization at one project — irrelevant to what this test is
    # actually verifying (query-level scoping), so it's bypassed rather than
    # worked around with a second signup/Organization.
    async with session_scope(organization_id=organization_id) as session:
        project_b_row = Project(organization_id=uuid.UUID(organization_id), name="Project B", url="https://example.com")
        session.add(project_b_row)
        await session.flush()
        project_b = str(project_b_row.id)
    await _make_test_case(organization_id=organization_id, project_id=project_a, title="Case in A")
    await _make_test_case(organization_id=organization_id, project_id=project_b, title="Case in B")

    async with session_scope(organization_id=organization_id) as session:
        context_a = await context_builder.build_project_context(
            session, organization_id=uuid.UUID(organization_id), project_id=uuid.UUID(project_a)
        )

    assert context_a is not None
    titles = {tc["title"] for tc in context_a["test_cases"]}
    assert titles == {"Case in A"}
