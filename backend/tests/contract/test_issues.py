"""Contract tests for the Issues API (T167, contracts/issues-api.md):
CRUD, status lifecycle transitions, create-from-result, and attachments.
"""

import io
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


async def _signup_and_get_token(client, email="issues-contract@example.com"):
    r = await client.post(
        "/auth/signup", json={"email": email, "password": "correct horse battery staple", "name": "Issues Test"}
    )
    body = r.json()
    return body["access_token"], body["organization"]["id"]


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _create_project(client, token, name="Issues Project"):
    r = await client.post("/projects", json={"name": name, "url": "https://example.com"}, headers=_auth_headers(token))
    return r.json()["id"]


async def _point_project_at_fixture_site(*, organization_id: str, project_id: str, fixture_site_url: str) -> None:
    async with session_scope(organization_id=organization_id) as session:
        result = await session.execute(select(Project).where(Project.id == uuid.UUID(project_id)))
        project = result.scalar_one()
        project.url = fixture_site_url
        session.add(project)


async def _failed_result(client, token, organization_id, project_id, fixture_site_url):
    create = await client.post(
        f"/projects/{project_id}/test-cases",
        json={
            "title": "Failing",
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
    detail = await client.get(f"/projects/{project_id}/test-runs/{run_id}", headers=_auth_headers(token))
    result_id = detail.json()["results"][0]["id"]
    return case_id, run_id, result_id


async def test_create_issue_requires_authentication(client):
    response = await client.post(
        "/projects/00000000-0000-0000-0000-000000000000/issues",
        json={"title": "T", "description": "D", "severity": "minor", "priority": "low"},
    )
    assert response.status_code == 401


async def test_create_manual_issue(client):
    token, _org = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)

    response = await client.post(
        f"/projects/{project_id}/issues",
        json={"title": "Login button misaligned", "description": "Off by 4px on mobile", "severity": "minor", "priority": "low"},
        headers=_auth_headers(token),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Login button misaligned"
    assert body["status"] == "open"
    assert body["source_test_case_id"] is None
    assert body["source_test_run_id"] is None
    assert body["id"]


async def test_create_manual_issue_requires_severity_and_priority(client):
    token, _org = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)

    response = await client.post(
        f"/projects/{project_id}/issues", json={"title": "T", "description": "D"}, headers=_auth_headers(token)
    )

    assert response.status_code == 422


async def test_list_issues_filters_by_status_severity_priority(client):
    token, _org = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)
    await client.post(
        f"/projects/{project_id}/issues",
        json={"title": "Minor low", "description": "D", "severity": "minor", "priority": "low"},
        headers=_auth_headers(token),
    )
    await client.post(
        f"/projects/{project_id}/issues",
        json={"title": "Blocker critical", "description": "D", "severity": "blocker", "priority": "critical"},
        headers=_auth_headers(token),
    )

    all_response = await client.get(f"/projects/{project_id}/issues", headers=_auth_headers(token))
    assert len(all_response.json()["items"]) == 2

    by_severity = await client.get(f"/projects/{project_id}/issues?severity=blocker", headers=_auth_headers(token))
    assert [i["title"] for i in by_severity.json()["items"]] == ["Blocker critical"]

    by_priority = await client.get(f"/projects/{project_id}/issues?priority=low", headers=_auth_headers(token))
    assert [i["title"] for i in by_priority.json()["items"]] == ["Minor low"]

    by_status = await client.get(f"/projects/{project_id}/issues?status=resolved", headers=_auth_headers(token))
    assert by_status.json()["items"] == []


async def test_get_issue_detail(client):
    token, _org = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)
    create = await client.post(
        f"/projects/{project_id}/issues",
        json={"title": "T", "description": "D", "severity": "minor", "priority": "low"},
        headers=_auth_headers(token),
    )
    issue_id = create.json()["id"]

    response = await client.get(f"/projects/{project_id}/issues/{issue_id}", headers=_auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    assert body["issue"]["id"] == issue_id
    assert body["attachments"] == []
    assert body["source_test_case"] is None
    assert body["source_test_run"] is None


async def test_get_nonexistent_issue_returns_404(client):
    token, _org = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)

    response = await client.get(
        f"/projects/{project_id}/issues/00000000-0000-0000-0000-000000000000", headers=_auth_headers(token)
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_patch_issue_updates_fields(client):
    token, _org = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)
    create = await client.post(
        f"/projects/{project_id}/issues",
        json={"title": "T", "description": "D", "severity": "minor", "priority": "low"},
        headers=_auth_headers(token),
    )
    issue_id = create.json()["id"]

    response = await client.patch(
        f"/projects/{project_id}/issues/{issue_id}",
        json={"title": "Updated title", "severity": "critical"},
        headers=_auth_headers(token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Updated title"
    assert body["severity"] == "critical"
    assert body["description"] == "D"


@pytest.mark.parametrize(
    "sequence",
    [
        ["in_progress", "resolved", "closed"],
        ["in_progress", "wont_fix"],
        ["wont_fix"],
        ["resolved", "wont_fix"],
    ],
)
async def test_valid_status_transitions_from_non_terminal_states(client, sequence):
    token, _org = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)
    create = await client.post(
        f"/projects/{project_id}/issues",
        json={"title": "T", "description": "D", "severity": "minor", "priority": "low"},
        headers=_auth_headers(token),
    )
    issue_id = create.json()["id"]

    for status_value in sequence:
        response = await client.patch(
            f"/projects/{project_id}/issues/{issue_id}", json={"status": status_value}, headers=_auth_headers(token)
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == status_value


@pytest.mark.parametrize("terminal_status", ["closed", "wont_fix"])
@pytest.mark.parametrize("blocked_target", ["in_progress", "resolved"])
async def test_terminal_status_can_only_transition_to_open(client, terminal_status, blocked_target):
    token, _org = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)
    create = await client.post(
        f"/projects/{project_id}/issues",
        json={"title": "T", "description": "D", "severity": "minor", "priority": "low"},
        headers=_auth_headers(token),
    )
    issue_id = create.json()["id"]
    await client.patch(
        f"/projects/{project_id}/issues/{issue_id}", json={"status": terminal_status}, headers=_auth_headers(token)
    )

    blocked = await client.patch(
        f"/projects/{project_id}/issues/{issue_id}", json={"status": blocked_target}, headers=_auth_headers(token)
    )
    assert blocked.status_code == 422
    assert blocked.json()["error"]["code"] == "invalid_status_transition"

    reopened = await client.patch(
        f"/projects/{project_id}/issues/{issue_id}", json={"status": "open"}, headers=_auth_headers(token)
    )
    assert reopened.status_code == 200
    assert reopened.json()["status"] == "open"


async def test_create_issue_from_a_failed_result(client, fixture_site_url):
    token, organization_id = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)
    case_id, run_id, result_id = await _failed_result(client, token, organization_id, project_id, fixture_site_url)

    response = await client.post(
        f"/projects/{project_id}/issues/from-result/{result_id}",
        json={"severity": "major", "priority": "high"},
        headers=_auth_headers(token),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["source_test_case_id"] == case_id
    assert body["source_test_run_id"] == run_id
    assert body["title"]
    assert body["description"]
    assert body["severity"] == "major"
    assert body["priority"] == "high"

    detail = await client.get(f"/projects/{project_id}/issues/{body['id']}", headers=_auth_headers(token))
    detail_body = detail.json()
    assert len(detail_body["attachments"]) == 1
    assert detail_body["attachments"][0]["url"].startswith("http")
    assert detail_body["source_test_case"]["id"] == case_id
    assert detail_body["source_test_run"]["id"] == run_id


async def test_create_issue_from_result_allows_title_override(client, fixture_site_url):
    token, organization_id = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)
    _case_id, _run_id, result_id = await _failed_result(client, token, organization_id, project_id, fixture_site_url)

    response = await client.post(
        f"/projects/{project_id}/issues/from-result/{result_id}",
        json={"title": "Custom title", "description": "Custom description", "severity": "critical", "priority": "critical"},
        headers=_auth_headers(token),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Custom title"
    assert body["description"] == "Custom description"


async def test_create_issue_from_a_passing_result_is_still_allowed_with_no_screenshot(client, fixture_site_url):
    """FR-087 scopes the pre-fill convenience to failed results, but does
    not itself forbid filing an issue from a passing result's id (e.g. a
    user noticing a different problem while reviewing it) — the contract's
    only documented error is result_not_found (nonexistent id), not
    "result not failed"."""
    token, organization_id = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)
    case_id = (
        await client.post(
            f"/projects/{project_id}/test-cases",
            json={
                "title": "Passing",
                "description": "D",
                "priority": "low",
                "severity": "minor",
                "steps": [
                    {"action_type": "navigate", "target_descriptor": fixture_site_url},
                    {"action_type": "assert_content", "expected_assertion": "Fixture Home"},
                ],
            },
            headers=_auth_headers(token),
        )
    ).json()["id"]
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
    detail = await client.get(f"/projects/{project_id}/test-runs/{run_id}", headers=_auth_headers(token))
    result_id = detail.json()["results"][0]["id"]

    response = await client.post(
        f"/projects/{project_id}/issues/from-result/{result_id}",
        json={"severity": "minor", "priority": "low"},
        headers=_auth_headers(token),
    )
    assert response.status_code == 201
    detail_response = await client.get(
        f"/projects/{project_id}/issues/{response.json()['id']}", headers=_auth_headers(token)
    )
    assert detail_response.json()["attachments"] == []


async def test_create_issue_from_nonexistent_result_returns_404(client):
    token, _org = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)

    response = await client.post(
        f"/projects/{project_id}/issues/from-result/00000000-0000-0000-0000-000000000000",
        json={"severity": "minor", "priority": "low"},
        headers=_auth_headers(token),
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "result_not_found"


async def test_add_attachment_from_existing_storage_key(client, fixture_site_url):
    token, organization_id = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)
    _case_id, _run_id, result_id = await _failed_result(client, token, organization_id, project_id, fixture_site_url)
    from_result = await client.post(
        f"/projects/{project_id}/issues/from-result/{result_id}",
        json={"severity": "major", "priority": "high"},
        headers=_auth_headers(token),
    )
    issue_id = from_result.json()["id"]

    # Reference a real, already-uploaded artifact this Organization owns
    # (the "existing artifact" variant of the contract's attachments
    # endpoint) — fetched directly from the DB since the API only ever
    # exposes a signed URL, never the raw storage_key (SEC-013).
    from testpilot.execution.artifact_models import Artifact

    async with session_scope(organization_id=organization_id) as session:
        artifact_result = await session.execute(
            select(Artifact).where(Artifact.test_result_id == uuid.UUID(result_id))
        )
        existing_storage_key = artifact_result.scalars().first().storage_key

    response = await client.post(
        f"/projects/{project_id}/issues/{issue_id}/attachments",
        json={"storage_key": existing_storage_key, "type": "log"},
        headers=_auth_headers(token),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["type"] == "log"

    detail = await client.get(f"/projects/{project_id}/issues/{issue_id}", headers=_auth_headers(token))
    # The from-result screenshot plus this manually attached log (same key).
    assert len(detail.json()["attachments"]) == 2


async def test_add_attachment_rejects_a_storage_key_the_organization_does_not_own(client):
    """SEC-011: an attacker-supplied storage_key that doesn't correspond to
    anything this Organization actually owns must be rejected, not silently
    minted a signed URL for whatever object happens to be at that key."""
    token, _org = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)
    issue = await client.post(
        f"/projects/{project_id}/issues",
        json={"title": "T", "description": "D", "severity": "minor", "priority": "low"},
        headers=_auth_headers(token),
    )
    issue_id = issue.json()["id"]

    response = await client.post(
        f"/projects/{project_id}/issues/{issue_id}/attachments",
        json={"storage_key": f"artifacts/{uuid.uuid4()}", "type": "log"},
        headers=_auth_headers(token),
    )

    assert response.status_code == 404


async def test_add_attachment_rejects_a_malformed_json_body(client):
    """T206/FR-130: the JSON branch of this dual-format endpoint bypasses
    FastAPI's normal Pydantic body validation (it reads request.json()
    directly, since one route can't declare both a file body and a JSON
    body — see the route's own docstring) — a missing/malformed field must
    still be rejected as a clean 422, not surfaced as an unhandled 500."""
    token, _org = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)
    issue = await client.post(
        f"/projects/{project_id}/issues",
        json={"title": "T", "description": "D", "severity": "minor", "priority": "low"},
        headers=_auth_headers(token),
    )
    issue_id = issue.json()["id"]

    missing_key_response = await client.post(
        f"/projects/{project_id}/issues/{issue_id}/attachments",
        json={"type": "log"},
        headers=_auth_headers(token),
    )
    assert missing_key_response.status_code == 422
    assert missing_key_response.json()["error"]["code"] == "validation_failed"

    invalid_type_response = await client.post(
        f"/projects/{project_id}/issues/{issue_id}/attachments",
        json={"storage_key": "artifacts/whatever", "type": "not-a-real-type"},
        headers=_auth_headers(token),
    )
    assert invalid_type_response.status_code == 422
    assert invalid_type_response.json()["error"]["code"] == "validation_failed"


async def test_add_attachment_via_multipart_upload(client):
    token, _org = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)
    issue = await client.post(
        f"/projects/{project_id}/issues",
        json={"title": "T", "description": "D", "severity": "minor", "priority": "low"},
        headers=_auth_headers(token),
    )
    issue_id = issue.json()["id"]

    response = await client.post(
        f"/projects/{project_id}/issues/{issue_id}/attachments",
        files={"file": ("note.txt", io.BytesIO(b"a log excerpt"), "text/plain")},
        data={"type": "log"},
        headers=_auth_headers(token),
    )

    assert response.status_code == 201
    detail = await client.get(f"/projects/{project_id}/issues/{issue_id}", headers=_auth_headers(token))
    assert len(detail.json()["attachments"]) == 1
    assert detail.json()["attachments"][0]["url"].startswith("http")


async def test_add_attachment_rejects_disallowed_content_type(client):
    token, _org = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)
    issue = await client.post(
        f"/projects/{project_id}/issues",
        json={"title": "T", "description": "D", "severity": "minor", "priority": "low"},
        headers=_auth_headers(token),
    )
    issue_id = issue.json()["id"]

    response = await client.post(
        f"/projects/{project_id}/issues/{issue_id}/attachments",
        files={"file": ("script.exe", io.BytesIO(b"MZ..."), "application/x-msdownload")},
        data={"type": "log"},
        headers=_auth_headers(token),
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_file_type"


async def test_add_attachment_rejects_an_oversized_file(client):
    token, _org = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)
    issue = await client.post(
        f"/projects/{project_id}/issues",
        json={"title": "T", "description": "D", "severity": "minor", "priority": "low"},
        headers=_auth_headers(token),
    )
    issue_id = issue.json()["id"]

    oversized = b"x" * (6 * 1024 * 1024)  # over the 5MB limit
    response = await client.post(
        f"/projects/{project_id}/issues/{issue_id}/attachments",
        files={"file": ("big.png", io.BytesIO(oversized), "image/png")},
        data={"type": "screenshot"},
        headers=_auth_headers(token),
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "file_too_large"


async def test_issue_from_another_organization_is_not_found(client):
    """FR-138/SEC-011: cross-tenant access returns 404, never 403."""
    token_a, _org_a = await _signup_and_get_token(client, email="issues-org-a@example.com")
    project_id_a = await _create_project(client, token_a)
    create = await client.post(
        f"/projects/{project_id_a}/issues",
        json={"title": "T", "description": "D", "severity": "minor", "priority": "low"},
        headers=_auth_headers(token_a),
    )
    issue_id_a = create.json()["id"]

    token_b, _org_b = await _signup_and_get_token(client, email="issues-org-b@example.com")
    project_id_b = await _create_project(client, token_b)

    response = await client.get(f"/projects/{project_id_b}/issues/{issue_id_a}", headers=_auth_headers(token_b))
    assert response.status_code == 404
