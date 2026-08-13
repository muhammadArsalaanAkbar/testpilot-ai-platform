"""Contract test for POST /assistant/chat (T181, T177 data model already in
place). Written before the route exists — MUST fail (404) until T179
implements the 501 stub. Future scope (FR-097-FR-103): the endpoint is a
documented not-implemented stub, not a working chat, per Phase 15's
"Scaffold Only" goal — this test asserts the app degrades honestly instead
of erroring or silently 404ing on an undocumented path.
"""

import pytest


async def _signup_and_get_token(client, email="assistant-stub@example.com"):
    r = await client.post(
        "/auth/signup", json={"email": email, "password": "correct horse battery staple", "name": "Assistant Stub"}
    )
    return r.json()["access_token"]


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.anyio
async def test_chat_is_not_implemented_yet(client):
    """T177: schema exists, route is a documented 501 stub (Future scope)."""
    token = await _signup_and_get_token(client)
    response = await client.post("/assistant/chat", json={"message": "What is my pass rate?"}, headers=_auth_headers(token))
    assert response.status_code == 501
    assert response.json()["error"]["code"] == "not_implemented"


@pytest.mark.anyio
async def test_chat_requires_authentication(client):
    response = await client.post("/assistant/chat", json={"message": "hello"})
    assert response.status_code == 401
