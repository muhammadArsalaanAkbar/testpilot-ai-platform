"""T220: `projects.service.get_project`'s caching (NFR-008) must never
leak a cross-tenant read, and every write path must invalidate its cache
entry so a stale value is never served after an update/archive/unarchive/
delete. Exercised via the real HTTP API (not the service function
directly) so this proves genuine, observable behavior, not just that the
right internal functions were called.
"""

import pytest

pytestmark = pytest.mark.anyio


async def _signup_and_get_token(client, email: str) -> str:
    r = await client.post(
        "/auth/signup", json={"email": email, "password": "correct horse battery staple", "name": "Cache Test"}
    )
    return r.json()["access_token"]


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_updated_project_name_is_visible_immediately_not_the_stale_cached_value(client):
    token = await _signup_and_get_token(client, "cache-update@example.com")
    create = await client.post(
        "/projects", json={"name": "Original Name", "url": "https://example.com"}, headers=_auth_headers(token)
    )
    project_id = create.json()["id"]

    # Populate the cache with the pre-update value.
    first_read = await client.get(f"/projects/{project_id}", headers=_auth_headers(token))
    assert first_read.json()["project"]["name"] == "Original Name"

    await client.patch(f"/projects/{project_id}", json={"name": "Updated Name"}, headers=_auth_headers(token))

    second_read = await client.get(f"/projects/{project_id}", headers=_auth_headers(token))
    assert second_read.json()["project"]["name"] == "Updated Name"


async def test_archived_status_is_visible_immediately_not_the_stale_cached_value(client):
    token = await _signup_and_get_token(client, "cache-archive@example.com")
    create = await client.post(
        "/projects", json={"name": "Archive Me", "url": "https://example.com"}, headers=_auth_headers(token)
    )
    project_id = create.json()["id"]

    first_read = await client.get(f"/projects/{project_id}", headers=_auth_headers(token))
    assert first_read.json()["project"]["status"] == "active"

    await client.post(f"/projects/{project_id}/archive", headers=_auth_headers(token))

    second_read = await client.get(f"/projects/{project_id}", headers=_auth_headers(token))
    assert second_read.json()["project"]["status"] == "archived"


async def test_deleted_project_returns_not_found_even_if_it_was_cached(client):
    token = await _signup_and_get_token(client, "cache-delete@example.com")
    create = await client.post(
        "/projects", json={"name": "Delete Me", "url": "https://example.com"}, headers=_auth_headers(token)
    )
    project_id = create.json()["id"]

    first_read = await client.get(f"/projects/{project_id}", headers=_auth_headers(token))
    assert first_read.status_code == 200

    delete = await client.request(
        "DELETE", f"/projects/{project_id}", json={"confirm": True}, headers=_auth_headers(token)
    )
    assert delete.status_code == 204

    second_read = await client.get(f"/projects/{project_id}", headers=_auth_headers(token))
    assert second_read.status_code == 404


async def test_a_cached_project_is_never_visible_to_a_different_organization(client):
    """The critical security property (FR-136/SEC-011): the cache key
    itself must be scoped by organization_id, not just project_id — an
    attacker whose own read populates nothing relevant, then guesses/reuses
    another Organization's project_id, must still get 404, exactly as
    though nothing were cached at all."""
    token_a = await _signup_and_get_token(client, "cache-tenant-a@example.com")
    create = await client.post(
        "/projects", json={"name": "Org A Project", "url": "https://example.com"}, headers=_auth_headers(token_a)
    )
    project_id = create.json()["id"]

    # Populate the cache as Org A.
    own_read = await client.get(f"/projects/{project_id}", headers=_auth_headers(token_a))
    assert own_read.status_code == 200

    token_b = await _signup_and_get_token(client, "cache-tenant-b@example.com")
    cross_tenant_read = await client.get(f"/projects/{project_id}", headers=_auth_headers(token_b))
    assert cross_tenant_read.status_code == 404
    assert cross_tenant_read.json()["error"]["code"] == "not_found"
