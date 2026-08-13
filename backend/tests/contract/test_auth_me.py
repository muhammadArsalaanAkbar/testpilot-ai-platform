"""Contract test for GET/PATCH/DELETE /auth/me, /auth/me/change-password,
/auth/me/sessions (contracts/auth-api.md; T056, T241/DATA-004)."""

import pytest


async def _signup_and_get_token(client, email="me-contract@example.com", password="correct horse battery staple"):
    r = await client.post("/auth/signup", json={"email": email, "password": password, "name": "Me Contract"})
    return r.json()["access_token"]


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.anyio
async def test_get_me_requires_authentication(client):
    response = await client.get("/auth/me")
    assert response.status_code == 401


@pytest.mark.anyio
async def test_get_me_returns_user_org_and_role(client):
    token = await _signup_and_get_token(client)
    response = await client.get("/auth/me", headers=_auth_headers(token))
    assert response.status_code == 200
    body = response.json()
    assert body["user"]["email"] == "me-contract@example.com"
    assert body["organization"]["name"]
    assert body["role"] == "owner"


@pytest.mark.anyio
async def test_patch_me_updates_name(client):
    token = await _signup_and_get_token(client)
    response = await client.patch("/auth/me", json={"name": "New Name"}, headers=_auth_headers(token))
    assert response.status_code == 200
    assert response.json()["user"]["name"] == "New Name"


@pytest.mark.anyio
async def test_patch_me_rejects_taken_email(client):
    await client.post(
        "/auth/signup", json={"email": "taken@example.com", "password": "correct horse battery staple", "name": "Taken"}
    )
    token = await _signup_and_get_token(client)
    response = await client.patch("/auth/me", json={"email": "taken@example.com"}, headers=_auth_headers(token))
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "email_taken"


@pytest.mark.anyio
async def test_change_password_with_correct_current_password(client):
    token = await _signup_and_get_token(client)
    response = await client.post(
        "/auth/me/change-password",
        json={"current_password": "correct horse battery staple", "new_password": "a brand new password"},
        headers=_auth_headers(token),
    )
    assert response.status_code == 200

    old_login = await client.post(
        "/auth/login", json={"email": "me-contract@example.com", "password": "correct horse battery staple"}
    )
    assert old_login.status_code == 401

    new_login = await client.post(
        "/auth/login", json={"email": "me-contract@example.com", "password": "a brand new password"}
    )
    assert new_login.status_code == 200


@pytest.mark.anyio
async def test_change_password_rejects_wrong_current_password(client):
    token = await _signup_and_get_token(client)
    response = await client.post(
        "/auth/me/change-password",
        json={"current_password": "totally wrong", "new_password": "a brand new password"},
        headers=_auth_headers(token),
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_current_password"


@pytest.mark.anyio
async def test_sessions_list_shows_current_session(client):
    token = await _signup_and_get_token(client)
    response = await client.get("/auth/me/sessions", headers=_auth_headers(token))
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["is_current"] is True


@pytest.mark.anyio
async def test_revoke_session_removes_it_from_list(client):
    token = await _signup_and_get_token(client)
    sessions = await client.get("/auth/me/sessions", headers=_auth_headers(token))
    session_id = sessions.json()["items"][0]["id"]

    revoke = await client.delete(f"/auth/me/sessions/{session_id}", headers=_auth_headers(token))
    assert revoke.status_code == 204

    after = await client.get("/auth/me/sessions", headers=_auth_headers(token))
    assert after.json()["items"] == []


@pytest.mark.anyio
async def test_delete_account_anonymizes_and_prevents_login(client):
    token = await _signup_and_get_token(client)
    response = await client.delete("/auth/me", headers=_auth_headers(token))
    assert response.status_code == 204

    login = await client.post(
        "/auth/login", json={"email": "me-contract@example.com", "password": "correct horse battery staple"}
    )
    assert login.status_code == 401

    # Access token was already issued before deletion — subsequent requests
    # under it should still work only until it naturally expires (JWTs are
    # stateless), but the underlying account must no longer be reachable by
    # its original email.
