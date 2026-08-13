"""Contract tests for AI test-case generation endpoints (T108,
contracts/test-cases-api.md). These cover the HTTP/enqueue layer only —
job COMPLETION (a worker actually processing the queue and producing a
positive/negative/edge-case mix) is verified by
tests/integration/test_ai_generation_flow.py (T110).
"""

import pytest


async def _signup_and_get_token(client, email="ai-gen-contract@example.com"):
    r = await client.post(
        "/auth/signup", json={"email": email, "password": "correct horse battery staple", "name": "AI Gen Test"}
    )
    return r.json()["access_token"]


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _create_project(client, token, name="AI Gen Project"):
    r = await client.post("/projects", json={"name": name, "url": "https://example.com"}, headers=_auth_headers(token))
    return r.json()["id"]


@pytest.mark.anyio
async def test_generate_requires_authentication(client):
    response = await client.post("/projects/00000000-0000-0000-0000-000000000000/test-cases/generate")
    assert response.status_code == 401


@pytest.mark.anyio
async def test_generate_returns_202_with_a_queued_run(client):
    token = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)

    response = await client.post(f"/projects/{project_id}/test-cases/generate", headers=_auth_headers(token))

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "queued"
    assert body["scope"] == "full_batch"
    assert body["project_id"] == project_id
    assert body["created_test_case_ids"] == []
    assert body["failure_reason"] is None
    assert body["id"]


@pytest.mark.anyio
async def test_generate_twice_concurrently_returns_409(client):
    token = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)

    first = await client.post(f"/projects/{project_id}/test-cases/generate", headers=_auth_headers(token))
    assert first.status_code == 202

    second = await client.post(f"/projects/{project_id}/test-cases/generate", headers=_auth_headers(token))
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "generation_in_progress"


@pytest.mark.anyio
async def test_generate_for_archived_project_returns_409(client):
    token = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)
    await client.post(f"/projects/{project_id}/archive", headers=_auth_headers(token))

    response = await client.post(f"/projects/{project_id}/test-cases/generate", headers=_auth_headers(token))

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "project_archived"


@pytest.mark.anyio
async def test_get_generation_run_status(client):
    token = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)
    generate = await client.post(f"/projects/{project_id}/test-cases/generate", headers=_auth_headers(token))
    run_id = generate.json()["id"]

    response = await client.get(f"/projects/{project_id}/test-cases/generate/{run_id}", headers=_auth_headers(token))

    assert response.status_code == 200
    assert response.json()["id"] == run_id
    assert response.json()["status"] == "queued"


@pytest.mark.anyio
async def test_get_nonexistent_generation_run_returns_404(client):
    token = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)

    response = await client.get(
        f"/projects/{project_id}/test-cases/generate/00000000-0000-0000-0000-000000000000",
        headers=_auth_headers(token),
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


@pytest.mark.anyio
async def test_regenerate_returns_202_with_single_case_scope(client):
    token = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)
    create = await client.post(
        f"/projects/{project_id}/test-cases",
        json={"title": "T", "description": "D", "priority": "low", "severity": "minor"},
        headers=_auth_headers(token),
    )
    test_case_id = create.json()["id"]

    response = await client.post(
        f"/projects/{project_id}/test-cases/{test_case_id}/regenerate", headers=_auth_headers(token)
    )

    assert response.status_code == 202
    body = response.json()
    assert body["scope"] == "single_case"
    assert body["status"] == "queued"


@pytest.mark.anyio
async def test_generate_and_regenerate_conflict_with_each_other(client):
    """FR-047's concurrency guard is per-project, not per-endpoint — a
    full-batch generate blocks a subsequent regenerate for the same
    project, and vice versa."""
    token = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)
    create = await client.post(
        f"/projects/{project_id}/test-cases",
        json={"title": "T", "description": "D", "priority": "low", "severity": "minor"},
        headers=_auth_headers(token),
    )
    test_case_id = create.json()["id"]

    generate = await client.post(f"/projects/{project_id}/test-cases/generate", headers=_auth_headers(token))
    assert generate.status_code == 202

    regenerate = await client.post(
        f"/projects/{project_id}/test-cases/{test_case_id}/regenerate", headers=_auth_headers(token)
    )
    assert regenerate.status_code == 409
    assert regenerate.json()["error"]["code"] == "generation_in_progress"
