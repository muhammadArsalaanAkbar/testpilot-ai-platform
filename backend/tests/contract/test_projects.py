"""Contract tests for the Projects API (contracts/projects-api.md, T085).

`https://example.com` is used for "valid public URL" cases — DNS resolution
is real here (the SSRF guard has no per-request override at the HTTP layer,
by design: production traffic never gets to inject a fake resolver either).
Private/loopback literal IPs need no DNS round-trip, so they're cheap and
deterministic.
"""

import pytest


async def _signup_and_get_token(client, email="projects-contract@example.com"):
    r = await client.post(
        "/auth/signup", json={"email": email, "password": "correct horse battery staple", "name": "Projects Test"}
    )
    return r.json()["access_token"]


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.anyio
async def test_create_project_requires_authentication(client):
    response = await client.post("/projects", json={"name": "P", "url": "https://example.com"})
    assert response.status_code == 401


@pytest.mark.anyio
async def test_create_project_succeeds_with_a_valid_public_url(client):
    token = await _signup_and_get_token(client)
    response = await client.post(
        "/projects", json={"name": "My Site", "url": "https://example.com"}, headers=_auth_headers(token)
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "My Site"
    assert body["url"] == "https://example.com"
    assert body["status"] == "active"
    assert body["settings"] == {}
    assert body["id"]
    assert body["created_at"]


@pytest.mark.anyio
async def test_create_project_rejects_malformed_url(client):
    token = await _signup_and_get_token(client)
    response = await client.post(
        "/projects", json={"name": "Bad", "url": "not-a-url"}, headers=_auth_headers(token)
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_url"


@pytest.mark.anyio
async def test_create_project_rejects_private_ip_url(client):
    token = await _signup_and_get_token(client)
    response = await client.post(
        "/projects", json={"name": "Internal", "url": "http://127.0.0.1/admin"}, headers=_auth_headers(token)
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "url_not_public"


@pytest.mark.anyio
async def test_list_projects_filters_by_status(client):
    token = await _signup_and_get_token(client)
    create = await client.post(
        "/projects", json={"name": "Filterable", "url": "https://example.com"}, headers=_auth_headers(token)
    )
    project_id = create.json()["id"]

    active_list = await client.get("/projects?status_filter=active", headers=_auth_headers(token))
    assert active_list.status_code == 200
    assert any(p["id"] == project_id for p in active_list.json()["items"])

    archived_list = await client.get("/projects?status_filter=archived", headers=_auth_headers(token))
    assert archived_list.status_code == 200
    assert not any(p["id"] == project_id for p in archived_list.json()["items"])

    await client.post(f"/projects/{project_id}/archive", headers=_auth_headers(token))

    archived_list_after = await client.get("/projects?status_filter=archived", headers=_auth_headers(token))
    assert any(p["id"] == project_id for p in archived_list_after.json()["items"])


@pytest.mark.anyio
async def test_get_project_returns_detail_with_empty_recent_runs(client):
    token = await _signup_and_get_token(client)
    create = await client.post(
        "/projects", json={"name": "Detail Me", "url": "https://example.com"}, headers=_auth_headers(token)
    )
    project_id = create.json()["id"]

    response = await client.get(f"/projects/{project_id}", headers=_auth_headers(token))
    assert response.status_code == 200
    body = response.json()
    assert body["project"]["id"] == project_id
    assert body["recent_runs"] == []


@pytest.mark.anyio
async def test_get_nonexistent_project_returns_404(client):
    token = await _signup_and_get_token(client)
    response = await client.get(
        "/projects/00000000-0000-0000-0000-000000000000", headers=_auth_headers(token)
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


@pytest.mark.anyio
async def test_project_from_another_organization_is_not_found(client):
    """Cross-tenant access must be indistinguishable from a nonexistent
    resource (FR-136/SEC-011) — no 403 anywhere in this API."""
    token_a = await _signup_and_get_token(client, email="projects-org-a@example.com")
    create = await client.post(
        "/projects", json={"name": "Org A Project", "url": "https://example.com"}, headers=_auth_headers(token_a)
    )
    project_id = create.json()["id"]

    token_b = await _signup_and_get_token(client, email="projects-org-b@example.com")
    response = await client.get(f"/projects/{project_id}", headers=_auth_headers(token_b))
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


@pytest.mark.anyio
async def test_update_project_name_and_url(client):
    token = await _signup_and_get_token(client)
    create = await client.post(
        "/projects", json={"name": "Old Name", "url": "https://example.com"}, headers=_auth_headers(token)
    )
    project_id = create.json()["id"]

    response = await client.patch(
        f"/projects/{project_id}", json={"name": "New Name"}, headers=_auth_headers(token)
    )
    assert response.status_code == 200
    assert response.json()["name"] == "New Name"
    assert response.json()["url"] == "https://example.com"


@pytest.mark.anyio
async def test_update_project_rejects_private_ip_url(client):
    token = await _signup_and_get_token(client)
    create = await client.post(
        "/projects", json={"name": "Editable", "url": "https://example.com"}, headers=_auth_headers(token)
    )
    project_id = create.json()["id"]

    response = await client.patch(
        f"/projects/{project_id}", json={"url": "http://169.254.169.254/"}, headers=_auth_headers(token)
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "url_not_public"


@pytest.mark.anyio
async def test_archive_is_idempotent(client):
    token = await _signup_and_get_token(client)
    create = await client.post(
        "/projects", json={"name": "Archive Me", "url": "https://example.com"}, headers=_auth_headers(token)
    )
    project_id = create.json()["id"]

    first = await client.post(f"/projects/{project_id}/archive", headers=_auth_headers(token))
    assert first.status_code == 200
    assert first.json()["status"] == "archived"

    second = await client.post(f"/projects/{project_id}/archive", headers=_auth_headers(token))
    assert second.status_code == 200
    assert second.json()["status"] == "archived"


@pytest.mark.anyio
async def test_unarchive_restores_active_status(client):
    token = await _signup_and_get_token(client)
    create = await client.post(
        "/projects", json={"name": "Round Trip", "url": "https://example.com"}, headers=_auth_headers(token)
    )
    project_id = create.json()["id"]
    await client.post(f"/projects/{project_id}/archive", headers=_auth_headers(token))

    response = await client.post(f"/projects/{project_id}/unarchive", headers=_auth_headers(token))
    assert response.status_code == 200
    assert response.json()["status"] == "active"


@pytest.mark.anyio
async def test_delete_project_requires_confirmation(client):
    token = await _signup_and_get_token(client)
    create = await client.post(
        "/projects", json={"name": "Delete Me", "url": "https://example.com"}, headers=_auth_headers(token)
    )
    project_id = create.json()["id"]

    response = await client.request(
        "DELETE", f"/projects/{project_id}", json={"confirm": False}, headers=_auth_headers(token)
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "confirmation_required"


@pytest.mark.anyio
async def test_delete_project_succeeds_with_confirmation(client):
    token = await _signup_and_get_token(client)
    create = await client.post(
        "/projects", json={"name": "Delete Me For Real", "url": "https://example.com"}, headers=_auth_headers(token)
    )
    project_id = create.json()["id"]

    response = await client.request(
        "DELETE", f"/projects/{project_id}", json={"confirm": True}, headers=_auth_headers(token)
    )
    assert response.status_code == 204

    get_response = await client.get(f"/projects/{project_id}", headers=_auth_headers(token))
    assert get_response.status_code == 404
