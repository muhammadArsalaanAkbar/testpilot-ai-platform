"""Contract tests for the test-result detail endpoint (T146,
contracts/test-runs-api.md): `GET .../test-runs/{run_id}/results/{result_id}`
returns the execution log plus artifacts with signed URLs. Job COMPLETION
(a worker actually driving a real browser and producing a genuine result
with a real captured screenshot) is exercised by
tests/integration/test_execution_flow.py and test_artifact_storage.py;
these contract tests cover the HTTP response shape against results seeded
directly through the real runner.
"""

import uuid

import pytest
from sqlalchemy import select

from testpilot.core.db import session_scope
from testpilot.execution import runner
from testpilot.execution.playwright_engine import PlaywrightEngine
from testpilot.projects.models import Project

pytestmark = pytest.mark.anyio


async def _public_resolver(hostname: str) -> list[str]:
    return ["8.8.8.8"]


async def _signup_and_get_token(client, email="test-results-contract@example.com"):
    r = await client.post(
        "/auth/signup", json={"email": email, "password": "correct horse battery staple", "name": "Results Test"}
    )
    body = r.json()
    return body["access_token"], body["organization"]["id"]


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _create_project(client, token, name="Results Project"):
    r = await client.post("/projects", json={"name": name, "url": "https://example.com"}, headers=_auth_headers(token))
    return r.json()["id"]


async def _point_project_at_fixture_site(*, organization_id: str, project_id: str, fixture_site_url: str) -> None:
    async with session_scope(organization_id=organization_id) as session:
        result = await session.execute(select(Project).where(Project.id == uuid.UUID(project_id)))
        project = result.scalar_one()
        project.url = fixture_site_url
        session.add(project)


async def _create_approved_test_case(client, token, project_id, *, title, steps):
    create = await client.post(
        f"/projects/{project_id}/test-cases",
        json={"title": title, "description": "D", "priority": "low", "severity": "minor", "steps": steps},
        headers=_auth_headers(token),
    )
    test_case_id = create.json()["id"]
    await client.post(f"/projects/{project_id}/test-cases/{test_case_id}/approve", headers=_auth_headers(token))
    return test_case_id


async def _run_and_get_first_result(client, token, organization_id, project_id, case_id):
    create = await client.post(
        f"/projects/{project_id}/test-runs", json={"test_case_ids": [case_id]}, headers=_auth_headers(token)
    )
    run_id = create.json()["id"]

    engine = PlaywrightEngine(url_resolver=_public_resolver)
    try:
        await runner.run_test_run(test_run_id=uuid.UUID(run_id), organization_id=uuid.UUID(organization_id), engine=engine)
    finally:
        await engine.close()

    detail = await client.get(f"/projects/{project_id}/test-runs/{run_id}", headers=_auth_headers(token))
    result_id = detail.json()["results"][0]["id"]
    return run_id, result_id


async def test_get_result_detail_requires_authentication(client):
    response = await client.get(
        "/projects/00000000-0000-0000-0000-000000000000/test-runs/"
        "00000000-0000-0000-0000-000000000000/results/00000000-0000-0000-0000-000000000000"
    )
    assert response.status_code == 401


async def test_get_nonexistent_result_returns_404(client):
    token, _org = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)

    response = await client.get(
        f"/projects/{project_id}/test-runs/00000000-0000-0000-0000-000000000000/"
        f"results/00000000-0000-0000-0000-000000000000",
        headers=_auth_headers(token),
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_get_result_detail_for_a_passed_case_has_no_artifacts(client, fixture_site_url):
    token, organization_id = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)
    case_id = await _create_approved_test_case(
        client,
        token,
        project_id,
        title="Passing",
        steps=[
            {"action_type": "navigate", "target_descriptor": fixture_site_url},
            {"action_type": "assert_content", "expected_assertion": "Fixture Home"},
        ],
    )
    await _point_project_at_fixture_site(
        organization_id=organization_id, project_id=project_id, fixture_site_url=fixture_site_url
    )
    run_id, result_id = await _run_and_get_first_result(client, token, organization_id, project_id, case_id)

    response = await client.get(
        f"/projects/{project_id}/test-runs/{run_id}/results/{result_id}", headers=_auth_headers(token)
    )

    assert response.status_code == 200
    body = response.json()
    assert body["test_result"]["id"] == result_id
    assert body["test_result"]["status"] == "passed"
    assert len(body["execution_log"]) == 2
    assert body["execution_log"][0]["action_type"] == "navigate"
    assert body["artifacts"] == []
    assert body["ai_analyses"] == []


async def test_get_result_detail_for_a_failed_case_has_a_signed_screenshot_url(client, fixture_site_url):
    token, organization_id = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)
    case_id = await _create_approved_test_case(
        client,
        token,
        project_id,
        title="Failing",
        steps=[
            {"action_type": "navigate", "target_descriptor": fixture_site_url},
            {
                "action_type": "assert_element",
                "target_descriptor": "#does-not-exist",
                "expected_assertion": "present",
            },
        ],
    )
    await _point_project_at_fixture_site(
        organization_id=organization_id, project_id=project_id, fixture_site_url=fixture_site_url
    )
    run_id, result_id = await _run_and_get_first_result(client, token, organization_id, project_id, case_id)

    response = await client.get(
        f"/projects/{project_id}/test-runs/{run_id}/results/{result_id}", headers=_auth_headers(token)
    )

    assert response.status_code == 200
    body = response.json()
    assert body["test_result"]["status"] == "failed"
    assert body["test_result"]["failure_step_index"] == 1
    assert len(body["artifacts"]) == 1
    artifact = body["artifacts"][0]
    assert artifact["type"] == "screenshot"
    assert artifact["url"].startswith("http")
    assert artifact["captured_at"]


async def test_result_from_another_organization_is_not_found(client, fixture_site_url):
    """FR-138/SEC-011: cross-tenant access returns 404, never 403."""
    token_a, organization_id_a = await _signup_and_get_token(client, email="results-org-a@example.com")
    project_id_a = await _create_project(client, token_a)
    case_id_a = await _create_approved_test_case(
        client,
        token_a,
        project_id_a,
        title="A",
        steps=[{"action_type": "navigate", "target_descriptor": fixture_site_url}],
    )
    await _point_project_at_fixture_site(
        organization_id=organization_id_a, project_id=project_id_a, fixture_site_url=fixture_site_url
    )
    run_id_a, result_id_a = await _run_and_get_first_result(client, token_a, organization_id_a, project_id_a, case_id_a)

    token_b, _org_b = await _signup_and_get_token(client, email="results-org-b@example.com")
    project_id_b = await _create_project(client, token_b)

    response = await client.get(
        f"/projects/{project_id_b}/test-runs/{run_id_a}/results/{result_id_a}", headers=_auth_headers(token_b)
    )
    assert response.status_code == 404
