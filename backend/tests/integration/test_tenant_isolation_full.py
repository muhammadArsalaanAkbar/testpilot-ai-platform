"""T210: consolidated cross-tenant access security test pass (FR-136, SEC-011).

Confirms every resource type's fetch/action endpoints return 404
(`error.code == "not_found"`), never 403, when accessed with a valid access
token belonging to a different Organization than the one owning the
resource. Scattered single-resource variants of this check already exist in
several contract test files (test_projects.py, test_testcases.py, etc.);
this file is the single, comprehensive checkpoint the security requirement
itself asks for -- exercising every resource type in one place, including
two (notifications, reports) that had no prior cross-tenant coverage at
all.

Expensive-to-produce leaf resources (test results, AI analyses, generation
runs) are seeded by direct DB insert scoped to Org A's real
organization_id/project_id/test_case_id (obtained via the real HTTP
signup/project/test-case flow) rather than by running a real Playwright
execution or a real AI provider call -- this test is about the
authorization boundary, not about execution or AI correctness, both of
which are already covered elsewhere.
"""

import uuid

import pytest

from testpilot.ai_analysis.models import AIAnalysis, AIAnalysisStatus
from testpilot.ai_generation.models import GenerationRun, GenerationScope, GenerationStatus
from testpilot.core.db import session_scope
from testpilot.execution.models import TestResult, TestResultStatus
from testpilot.notifications.models import Notification, NotificationType


async def _signup(client, email: str) -> dict:
    r = await client.post(
        "/auth/signup",
        json={"email": email, "password": "correct horse battery staple", "name": "Tenant Isolation Test"},
    )
    assert r.status_code == 201
    return r.json()


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _create_project(client, token: str, name: str) -> str:
    r = await client.post(
        "/projects", json={"name": name, "url": "https://example.com"}, headers=_auth_headers(token)
    )
    assert r.status_code == 201
    return r.json()["id"]


async def _create_approved_test_case(client, token: str, project_id: str) -> str:
    r = await client.post(
        f"/projects/{project_id}/test-cases",
        json={
            "title": "Tenant Isolation Case",
            "description": "d",
            "priority": "medium",
            "severity": "minor",
            "steps": [{"action_type": "navigate", "target_descriptor": "https://example.com"}],
        },
        headers=_auth_headers(token),
    )
    assert r.status_code == 201
    test_case_id = r.json()["id"]
    approve = await client.post(
        f"/projects/{project_id}/test-cases/{test_case_id}/approve", headers=_auth_headers(token)
    )
    assert approve.status_code == 200
    return test_case_id


async def _create_test_run(client, token: str, project_id: str, test_case_id: str) -> str:
    r = await client.post(
        f"/projects/{project_id}/test-runs", json={"test_case_ids": [test_case_id]}, headers=_auth_headers(token)
    )
    assert r.status_code == 202
    return r.json()["id"]


async def _create_issue(client, token: str, project_id: str) -> str:
    r = await client.post(
        f"/projects/{project_id}/issues",
        json={"title": "Tenant Isolation Issue", "description": "d", "severity": "major", "priority": "high"},
        headers=_auth_headers(token),
    )
    assert r.status_code == 201
    return r.json()["id"]


async def _insert_test_result(*, organization_id: str, test_run_id: str, test_case_id: str) -> str:
    async with session_scope(organization_id=organization_id) as session:
        result = TestResult(
            organization_id=uuid.UUID(organization_id),
            test_run_id=uuid.UUID(test_run_id),
            test_case_id=uuid.UUID(test_case_id),
            status=TestResultStatus.failed,
            execution_log=[],
            failure_step_index=0,
            error_message="boom",
            duration_ms=100,
        )
        session.add(result)
        await session.flush()
        return str(result.id)


async def _insert_ai_analysis(*, organization_id: str, test_result_id: str) -> str:
    async with session_scope(organization_id=organization_id) as session:
        analysis = AIAnalysis(
            organization_id=uuid.UUID(organization_id),
            test_result_id=uuid.UUID(test_result_id),
            status=AIAnalysisStatus.completed,
            explanation="e",
            provider="anthropic",
            model="test-model",
        )
        session.add(analysis)
        await session.flush()
        return str(analysis.id)


async def _insert_generation_run(*, organization_id: str, project_id: str, requested_by_user_id: str) -> str:
    async with session_scope(organization_id=organization_id) as session:
        run = GenerationRun(
            organization_id=uuid.UUID(organization_id),
            project_id=uuid.UUID(project_id),
            requested_by_user_id=uuid.UUID(requested_by_user_id),
            scope=GenerationScope.full_batch,
            status=GenerationStatus.completed,
            created_test_case_ids=[],
        )
        session.add(run)
        await session.flush()
        return str(run.id)


async def _insert_notification(*, organization_id: str, user_id: str, related_entity_id: str) -> str:
    async with session_scope(organization_id=organization_id) as session:
        notification = Notification(
            organization_id=uuid.UUID(organization_id),
            user_id=uuid.UUID(user_id),
            type=NotificationType.run_completed,
            related_entity_type="test_run",
            related_entity_id=uuid.UUID(related_entity_id),
        )
        session.add(notification)
        await session.flush()
        return str(notification.id)


def _assert_not_found(response) -> None:
    assert response.status_code == 404, (
        f"expected 404 not_found for cross-tenant access, got {response.status_code}: {response.text}"
    )
    assert response.json()["error"]["code"] == "not_found"


@pytest.fixture
async def two_orgs(client):
    """Org A owns every resource under test; Org B is the attacker whose
    token is used for every cross-tenant request below."""
    org_a = await _signup(client, f"{uuid.uuid4()}@example.com")
    org_b = await _signup(client, f"{uuid.uuid4()}@example.com")
    token_a = org_a["access_token"]
    token_b = org_b["access_token"]
    organization_id_a = org_a["organization"]["id"]
    user_id_a = org_a["user"]["id"]

    project_id = await _create_project(client, token_a, "Tenant Isolation Project")
    test_case_id = await _create_approved_test_case(client, token_a, project_id)
    test_run_id = await _create_test_run(client, token_a, project_id, test_case_id)
    issue_id = await _create_issue(client, token_a, project_id)

    test_result_id = await _insert_test_result(
        organization_id=organization_id_a, test_run_id=test_run_id, test_case_id=test_case_id
    )
    analysis_id = await _insert_ai_analysis(organization_id=organization_id_a, test_result_id=test_result_id)
    generation_run_id = await _insert_generation_run(
        organization_id=organization_id_a, project_id=project_id, requested_by_user_id=user_id_a
    )
    notification_id = await _insert_notification(
        organization_id=organization_id_a, user_id=user_id_a, related_entity_id=test_run_id
    )

    return {
        "token_b": token_b,
        "project_id": project_id,
        "test_case_id": test_case_id,
        "test_run_id": test_run_id,
        "test_result_id": test_result_id,
        "analysis_id": analysis_id,
        "generation_run_id": generation_run_id,
        "issue_id": issue_id,
        "notification_id": notification_id,
    }


@pytest.mark.anyio
async def test_project_cross_tenant_get_is_not_found(client, two_orgs):
    response = await client.get(f"/projects/{two_orgs['project_id']}", headers=_auth_headers(two_orgs["token_b"]))
    _assert_not_found(response)


@pytest.mark.anyio
async def test_test_case_cross_tenant_get_is_not_found(client, two_orgs):
    response = await client.get(
        f"/projects/{two_orgs['project_id']}/test-cases/{two_orgs['test_case_id']}",
        headers=_auth_headers(two_orgs["token_b"]),
    )
    _assert_not_found(response)


@pytest.mark.anyio
async def test_test_case_cross_tenant_get_is_not_found_even_via_the_attackers_own_project(client, two_orgs):
    """Stronger IDOR check than the above: Org B has a real project of its
    own, and tries Org A's test_case_id nested under *that* project_id --
    the project_id path segment alone must not be enough to leak the
    resource's existence either."""
    own_project_id = await _create_project(client, two_orgs["token_b"], "Attacker Project")
    response = await client.get(
        f"/projects/{own_project_id}/test-cases/{two_orgs['test_case_id']}",
        headers=_auth_headers(two_orgs["token_b"]),
    )
    _assert_not_found(response)


@pytest.mark.anyio
async def test_generation_run_cross_tenant_get_is_not_found(client, two_orgs):
    response = await client.get(
        f"/projects/{two_orgs['project_id']}/test-cases/generate/{two_orgs['generation_run_id']}",
        headers=_auth_headers(two_orgs["token_b"]),
    )
    _assert_not_found(response)


@pytest.mark.anyio
async def test_test_run_cross_tenant_get_is_not_found(client, two_orgs):
    response = await client.get(
        f"/projects/{two_orgs['project_id']}/test-runs/{two_orgs['test_run_id']}",
        headers=_auth_headers(two_orgs["token_b"]),
    )
    _assert_not_found(response)


@pytest.mark.anyio
async def test_test_result_cross_tenant_get_is_not_found(client, two_orgs):
    response = await client.get(
        f"/projects/{two_orgs['project_id']}/test-runs/{two_orgs['test_run_id']}"
        f"/results/{two_orgs['test_result_id']}",
        headers=_auth_headers(two_orgs["token_b"]),
    )
    _assert_not_found(response)


@pytest.mark.anyio
async def test_ai_analysis_cross_tenant_get_is_not_found(client, two_orgs):
    response = await client.get(
        f"/projects/{two_orgs['project_id']}/test-runs/{two_orgs['test_run_id']}"
        f"/results/{two_orgs['test_result_id']}/analyses/{two_orgs['analysis_id']}",
        headers=_auth_headers(two_orgs["token_b"]),
    )
    _assert_not_found(response)


@pytest.mark.anyio
async def test_retry_failed_cross_tenant_is_not_found(client, two_orgs):
    response = await client.post(
        f"/projects/{two_orgs['project_id']}/test-runs/{two_orgs['test_run_id']}/retry-failed",
        headers=_auth_headers(two_orgs["token_b"]),
    )
    _assert_not_found(response)


@pytest.mark.anyio
async def test_issue_cross_tenant_get_is_not_found(client, two_orgs):
    response = await client.get(
        f"/projects/{two_orgs['project_id']}/issues/{two_orgs['issue_id']}",
        headers=_auth_headers(two_orgs["token_b"]),
    )
    _assert_not_found(response)


@pytest.mark.anyio
async def test_issue_cross_tenant_patch_is_not_found(client, two_orgs):
    response = await client.patch(
        f"/projects/{two_orgs['project_id']}/issues/{two_orgs['issue_id']}",
        json={"title": "Hijacked"},
        headers=_auth_headers(two_orgs["token_b"]),
    )
    _assert_not_found(response)


@pytest.mark.anyio
async def test_notification_cross_tenant_mark_read_is_not_found(client, two_orgs):
    response = await client.post(
        f"/notifications/{two_orgs['notification_id']}/read", headers=_auth_headers(two_orgs["token_b"])
    )
    _assert_not_found(response)


@pytest.mark.anyio
async def test_reports_summary_cross_tenant_is_not_found(client, two_orgs):
    response = await client.get(
        f"/projects/{two_orgs['project_id']}/reports/summary", headers=_auth_headers(two_orgs["token_b"])
    )
    _assert_not_found(response)


@pytest.mark.anyio
async def test_reports_issues_by_severity_cross_tenant_is_not_found(client, two_orgs):
    response = await client.get(
        f"/projects/{two_orgs['project_id']}/reports/issues-by-severity", headers=_auth_headers(two_orgs["token_b"])
    )
    _assert_not_found(response)


@pytest.mark.anyio
async def test_project_archive_cross_tenant_is_not_found(client, two_orgs):
    """Mutating actions must fail closed identically to reads -- archiving
    someone else's project must not even confirm it exists."""
    response = await client.post(
        f"/projects/{two_orgs['project_id']}/archive", headers=_auth_headers(two_orgs["token_b"])
    )
    _assert_not_found(response)


@pytest.mark.anyio
async def test_project_delete_cross_tenant_is_not_found(client, two_orgs):
    response = await client.request(
        "DELETE",
        f"/projects/{two_orgs['project_id']}",
        json={"confirm": True},
        headers=_auth_headers(two_orgs["token_b"]),
    )
    _assert_not_found(response)


@pytest.mark.anyio
async def test_no_cross_tenant_response_in_this_file_is_a_403(client, two_orgs):
    """Belt-and-suspenders: exercise every cross-tenant request above in one
    place and assert none of them ever degrades to 403 -- a 403 (rather
    than 404) would itself leak that the resource exists in another
    Organization, which is exactly what SEC-011 forbids."""
    headers = _auth_headers(two_orgs["token_b"])
    requests = [
        ("GET", f"/projects/{two_orgs['project_id']}"),
        ("GET", f"/projects/{two_orgs['project_id']}/test-cases/{two_orgs['test_case_id']}"),
        ("GET", f"/projects/{two_orgs['project_id']}/test-runs/{two_orgs['test_run_id']}"),
        (
            "GET",
            f"/projects/{two_orgs['project_id']}/test-runs/{two_orgs['test_run_id']}"
            f"/results/{two_orgs['test_result_id']}",
        ),
        ("GET", f"/projects/{two_orgs['project_id']}/issues/{two_orgs['issue_id']}"),
        ("GET", f"/projects/{two_orgs['project_id']}/reports/summary"),
        ("POST", f"/notifications/{two_orgs['notification_id']}/read"),
    ]
    for method, path in requests:
        response = await client.request(method, path, headers=headers)
        assert response.status_code != 403, f"{method} {path} leaked existence via 403 instead of 404"
