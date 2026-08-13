"""Integration test: create-from-result copies attachments, and the link
survives an edit to the source test case (T168, FR-096).
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


async def _signup_and_get_token(client, email="issues-from-result@example.com"):
    r = await client.post(
        "/auth/signup", json={"email": email, "password": "correct horse battery staple", "name": "Issues From Result"}
    )
    body = r.json()
    return body["access_token"], body["organization"]["id"]


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _create_project(client, token, name="Issues From Result Project"):
    r = await client.post("/projects", json={"name": name, "url": "https://example.com"}, headers=_auth_headers(token))
    return r.json()["id"]


async def _point_project_at_fixture_site(*, organization_id: str, project_id: str, fixture_site_url: str) -> None:
    async with session_scope(organization_id=organization_id) as session:
        result = await session.execute(select(Project).where(Project.id == uuid.UUID(project_id)))
        project = result.scalar_one()
        project.url = fixture_site_url
        session.add(project)


async def test_create_from_result_copies_attachments_and_survives_a_source_case_edit(client, fixture_site_url):
    token, organization_id = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)

    create = await client.post(
        f"/projects/{project_id}/test-cases",
        json={
            "title": "Original title",
            "description": "D",
            "priority": "low",
            "severity": "minor",
            "steps": [
                {"action_type": "navigate", "target_descriptor": fixture_site_url},
                {"action_type": "assert_element", "target_descriptor": "#does-not-exist", "expected_assertion": "present"},
            ],
        },
        headers=_auth_headers(token),
    )
    case_id = create.json()["id"]
    await client.post(f"/projects/{project_id}/test-cases/{case_id}/approve", headers=_auth_headers(token))
    await _point_project_at_fixture_site(
        organization_id=organization_id, project_id=project_id, fixture_site_url=fixture_site_url
    )

    run_create = await client.post(
        f"/projects/{project_id}/test-runs", json={"test_case_ids": [case_id]}, headers=_auth_headers(token)
    )
    run_id = run_create.json()["id"]
    engine = PlaywrightEngine(url_resolver=_public_resolver)
    try:
        await runner.run_test_run(test_run_id=uuid.UUID(run_id), organization_id=uuid.UUID(organization_id), engine=engine)
    finally:
        await engine.close()
    run_detail = await client.get(f"/projects/{project_id}/test-runs/{run_id}", headers=_auth_headers(token))
    result_id = run_detail.json()["results"][0]["id"]

    result_detail = await client.get(
        f"/projects/{project_id}/test-runs/{run_id}/results/{result_id}", headers=_auth_headers(token)
    )
    source_artifact_urls = {a["id"]: a["url"] for a in result_detail.json()["artifacts"]}
    assert len(source_artifact_urls) == 1

    issue_response = await client.post(
        f"/projects/{project_id}/issues/from-result/{result_id}",
        json={"severity": "major", "priority": "high"},
        headers=_auth_headers(token),
    )
    assert issue_response.status_code == 201
    issue_id = issue_response.json()["id"]
    original_title = issue_response.json()["title"]

    issue_detail = await client.get(f"/projects/{project_id}/issues/{issue_id}", headers=_auth_headers(token))
    issue_body = issue_detail.json()
    assert len(issue_body["attachments"]) == 1
    assert issue_body["attachments"][0]["type"] == "screenshot"
    assert issue_body["attachments"][0]["url"].startswith("http")
    assert issue_body["source_test_case"]["id"] == case_id
    assert issue_body["source_test_case"]["title"] == "Original title"

    # FR-096: edit the source test case — the issue's link (and its own
    # already-captured title/description snapshot) must survive unchanged.
    await client.patch(
        f"/projects/{project_id}/test-cases/{case_id}",
        json={"title": "Edited title", "steps": []},
        headers=_auth_headers(token),
    )

    issue_after_edit = await client.get(f"/projects/{project_id}/issues/{issue_id}", headers=_auth_headers(token))
    after_body = issue_after_edit.json()
    assert after_body["issue"]["title"] == original_title
    assert after_body["issue"]["source_test_case_id"] == case_id
    assert after_body["source_test_case"]["id"] == case_id
    assert after_body["source_test_case"]["title"] == "Edited title"
    assert len(after_body["attachments"]) == 1


async def test_create_from_result_survives_a_second_run_of_the_same_case(client, fixture_site_url):
    """FR-096: "or the run's data is superseded by newer runs" — a second,
    later run of the same case must not retroactively change which run/
    result an existing issue is linked to."""
    token, organization_id = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)
    create = await client.post(
        f"/projects/{project_id}/test-cases",
        json={
            "title": "Case",
            "description": "D",
            "priority": "low",
            "severity": "minor",
            "steps": [
                {"action_type": "navigate", "target_descriptor": fixture_site_url},
                {"action_type": "assert_element", "target_descriptor": "#does-not-exist", "expected_assertion": "present"},
            ],
        },
        headers=_auth_headers(token),
    )
    case_id = create.json()["id"]
    await client.post(f"/projects/{project_id}/test-cases/{case_id}/approve", headers=_auth_headers(token))
    await _point_project_at_fixture_site(
        organization_id=organization_id, project_id=project_id, fixture_site_url=fixture_site_url
    )

    async def _run_once() -> tuple[str, str]:
        run_create = await client.post(
            f"/projects/{project_id}/test-runs", json={"test_case_ids": [case_id]}, headers=_auth_headers(token)
        )
        run_id = run_create.json()["id"]
        engine = PlaywrightEngine(url_resolver=_public_resolver)
        try:
            await runner.run_test_run(
                test_run_id=uuid.UUID(run_id), organization_id=uuid.UUID(organization_id), engine=engine
            )
        finally:
            await engine.close()
        run_detail = await client.get(f"/projects/{project_id}/test-runs/{run_id}", headers=_auth_headers(token))
        return run_id, run_detail.json()["results"][0]["id"]

    first_run_id, first_result_id = await _run_once()
    issue_response = await client.post(
        f"/projects/{project_id}/issues/from-result/{first_result_id}",
        json={"severity": "major", "priority": "high"},
        headers=_auth_headers(token),
    )
    issue_id = issue_response.json()["id"]

    # A newer run happens after the issue was filed.
    await _run_once()

    issue_detail = await client.get(f"/projects/{project_id}/issues/{issue_id}", headers=_auth_headers(token))
    assert issue_detail.json()["issue"]["source_test_run_id"] == first_run_id
