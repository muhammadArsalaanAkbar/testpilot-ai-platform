"""Contract test for POST /auth/signup (contracts/auth-api.md).

Written before the endpoint exists (T046, constitution Principle III) — MUST
fail (404/connection-shaped failure) until T048/T055 implement it.
"""

import pytest


@pytest.mark.anyio
async def test_signup_creates_user_and_personal_organization(client):
    response = await client.post(
        "/auth/signup",
        json={"email": "new-user@example.com", "password": "correct horse battery staple", "name": "New User"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["user"]["email"] == "new-user@example.com"
    assert body["user"]["name"] == "New User"
    assert "password" not in body["user"]
    assert "password_hash" not in body["user"]
    assert body["organization"]["name"]
    assert "access_token" in body

    # FR-012: personal Organization auto-created 1:1 at signup.
    assert body["organization"]["id"]

    # Refresh token delivered as an httpOnly cookie, never in the body.
    assert "refresh_token" not in body
    set_cookie = response.headers.get("set-cookie", "")
    assert "HttpOnly" in set_cookie


@pytest.mark.anyio
async def test_signup_rejects_duplicate_email(client):
    payload = {"email": "dup@example.com", "password": "correct horse battery staple", "name": "First"}
    first = await client.post("/auth/signup", json=payload)
    assert first.status_code == 201

    second = await client.post(
        "/auth/signup",
        json={"email": "dup@example.com", "password": "another strong password", "name": "Second"},
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "email_taken"


@pytest.mark.anyio
async def test_signup_rejects_duplicate_email_case_insensitively(client):
    payload = {"email": "CaseTest@example.com", "password": "correct horse battery staple", "name": "First"}
    first = await client.post("/auth/signup", json=payload)
    assert first.status_code == 201

    second = await client.post(
        "/auth/signup",
        json={"email": "casetest@example.com", "password": "another strong password", "name": "Second"},
    )
    assert second.status_code == 409


@pytest.mark.anyio
async def test_signup_rejects_weak_password(client):
    response = await client.post(
        "/auth/signup",
        json={"email": "weak@example.com", "password": "123", "name": "Weak Password"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_failed"


@pytest.mark.anyio
async def test_signup_rejects_malformed_email(client):
    response = await client.post(
        "/auth/signup",
        json={"email": "not-an-email", "password": "correct horse battery staple", "name": "Bad Email"},
    )
    assert response.status_code == 422
