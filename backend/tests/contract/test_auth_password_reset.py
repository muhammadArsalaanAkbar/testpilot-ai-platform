"""Contract test for POST /auth/forgot-password, /auth/reset-password
(contracts/auth-api.md; spec Edge Cases: reused/expired reset tokens).
Written before the endpoints exist (T051, constitution Principle III) —
MUST fail until T050/T055 implement them."""

import re
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from testpilot.core.db import session_scope
from testpilot.core.email import test_outbox


def _extract_token(email_body: str) -> str:
    match = re.search(r"token=([A-Za-z0-9_-]+)", email_body)
    assert match, f"no reset token found in email body: {email_body!r}"
    return match.group(1)


async def _signup(client, email="reset-test@example.com", password="original strong password"):
    return await client.post("/auth/signup", json={"email": email, "password": password, "name": "Reset Test"})


@pytest.mark.anyio
async def test_forgot_password_always_returns_202(client):
    """FR-010: never reveals whether the email exists."""
    test_outbox.clear()
    known = await client.post("/auth/forgot-password", json={"email": "unknown@example.com"})
    assert known.status_code == 202
    assert test_outbox == []  # no email sent for an unknown address, but the response is identical


@pytest.mark.anyio
async def test_forgot_password_sends_reset_email_for_known_account(client):
    test_outbox.clear()
    await _signup(client)
    response = await client.post("/auth/forgot-password", json={"email": "reset-test@example.com"})
    assert response.status_code == 202
    assert len(test_outbox) == 1
    assert test_outbox[0].to == "reset-test@example.com"


@pytest.mark.anyio
async def test_reset_password_with_valid_token_changes_password_and_allows_login(client):
    test_outbox.clear()
    await _signup(client)
    await client.post("/auth/forgot-password", json={"email": "reset-test@example.com"})
    token = _extract_token(test_outbox[-1].body)

    reset = await client.post(
        "/auth/reset-password", json={"token": token, "new_password": "brand new strong password"}
    )
    assert reset.status_code == 200

    old_login = await client.post(
        "/auth/login", json={"email": "reset-test@example.com", "password": "original strong password"}
    )
    assert old_login.status_code == 401

    new_login = await client.post(
        "/auth/login", json={"email": "reset-test@example.com", "password": "brand new strong password"}
    )
    assert new_login.status_code == 200


@pytest.mark.anyio
async def test_reset_password_token_is_single_use(client):
    test_outbox.clear()
    await _signup(client)
    await client.post("/auth/forgot-password", json={"email": "reset-test@example.com"})
    token = _extract_token(test_outbox[-1].body)

    first = await client.post(
        "/auth/reset-password", json={"token": token, "new_password": "first new password"}
    )
    assert first.status_code == 200

    second = await client.post(
        "/auth/reset-password", json={"token": token, "new_password": "second new password"}
    )
    assert second.status_code == 400
    assert second.json()["error"]["code"] == "invalid_or_expired_token"


@pytest.mark.anyio
async def test_reset_password_rejects_expired_token(client):
    test_outbox.clear()
    await _signup(client)
    await client.post("/auth/forgot-password", json={"email": "reset-test@example.com"})
    token = _extract_token(test_outbox[-1].body)

    # Force the token's expiry into the past to simulate the spec's "reused/expired" edge case
    # without waiting out a real TTL.
    async with session_scope() as session:
        await session.execute(
            text("UPDATE password_reset_tokens SET expires_at = :expired WHERE token_hash IS NOT NULL"),
            {"expired": datetime.now(UTC) - timedelta(hours=1)},
        )

    response = await client.post(
        "/auth/reset-password", json={"token": token, "new_password": "irrelevant new password"}
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_or_expired_token"


@pytest.mark.anyio
async def test_reset_password_rejects_garbage_token(client):
    response = await client.post(
        "/auth/reset-password", json={"token": "not-a-real-token", "new_password": "irrelevant password"}
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_or_expired_token"
