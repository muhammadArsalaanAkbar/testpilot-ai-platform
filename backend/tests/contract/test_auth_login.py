"""Contract test for POST /auth/login, /auth/logout, /auth/refresh
(contracts/auth-api.md). Written before the endpoints exist (T047,
constitution Principle III) — MUST fail until T049/T055 implement them."""

import pytest


async def _signup(client, email="login-test@example.com", password="correct horse battery staple"):
    return await client.post("/auth/signup", json={"email": email, "password": password, "name": "Login Test"})


@pytest.mark.anyio
async def test_login_with_correct_credentials_succeeds(client):
    await _signup(client)
    response = await client.post(
        "/auth/login", json={"email": "login-test@example.com", "password": "correct horse battery staple"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["user"]["email"] == "login-test@example.com"
    assert "access_token" in body
    assert "HttpOnly" in response.headers.get("set-cookie", "")


@pytest.mark.anyio
async def test_login_with_wrong_password_rejected(client):
    await _signup(client)
    response = await client.post(
        "/auth/login", json={"email": "login-test@example.com", "password": "totally wrong password"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


@pytest.mark.anyio
async def test_login_with_nonexistent_email_returns_identical_error(client):
    """FR-010: identical response whether the account exists or not."""
    response = await client.post(
        "/auth/login", json={"email": "never-signed-up@example.com", "password": "whatever password"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


@pytest.mark.anyio
async def test_logout_revokes_the_session(client):
    await _signup(client)
    login = await client.post(
        "/auth/login", json={"email": "login-test@example.com", "password": "correct horse battery staple"}
    )
    access_token = login.json()["access_token"]

    logout = await client.post("/auth/logout", headers={"Authorization": f"Bearer {access_token}"})
    assert logout.status_code == 204

    # The refresh cookie was revoked server-side; refreshing must now fail.
    refresh = await client.post("/auth/refresh")
    assert refresh.status_code == 401


@pytest.mark.anyio
async def test_logout_all_revokes_every_session(client):
    """Distinct from `test_logout_revokes_the_session` (single session):
    two independent logins (two "devices", each with its own refresh
    cookie captured explicitly rather than relying on the shared client's
    single-slot cookie jar) must BOTH become invalid after one logout-all
    call, not just whichever session made the call."""
    await _signup(client, email="logout-all-test@example.com")

    login_a = await client.post(
        "/auth/login", json={"email": "logout-all-test@example.com", "password": "correct horse battery staple"}
    )
    refresh_token_a = login_a.cookies["refresh_token"]

    login_b = await client.post(
        "/auth/login", json={"email": "logout-all-test@example.com", "password": "correct horse battery staple"}
    )
    refresh_token_b = login_b.cookies["refresh_token"]
    access_token = login_b.json()["access_token"]

    assert refresh_token_a != refresh_token_b

    logout_all = await client.post("/auth/logout-all", headers={"Authorization": f"Bearer {access_token}"})
    assert logout_all.status_code == 204

    refresh_a = await client.post("/auth/refresh", cookies={"refresh_token": refresh_token_a})
    assert refresh_a.status_code == 401
    refresh_b = await client.post("/auth/refresh", cookies={"refresh_token": refresh_token_b})
    assert refresh_b.status_code == 401


@pytest.mark.anyio
async def test_refresh_issues_a_new_access_token(client):
    await _signup(client)
    login = await client.post(
        "/auth/login", json={"email": "login-test@example.com", "password": "correct horse battery staple"}
    )
    assert login.status_code == 200

    refresh = await client.post("/auth/refresh")
    assert refresh.status_code == 200
    assert "access_token" in refresh.json()


@pytest.mark.anyio
async def test_refresh_without_a_cookie_is_rejected(client):
    response = await client.post("/auth/refresh")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_or_expired_refresh_token"
