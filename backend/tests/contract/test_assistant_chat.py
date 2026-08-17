"""Contract tests for POST /assistant/chat (FR-097-FR-103).

Chat is synchronous (assistant/service.py's module docstring) — no
queue/poll layer to separately test the way ai_generation/ai_analysis split
"enqueue" (contract tests) from "job completion" (integration tests). These
tests cover the full HTTP request/response cycle against the real `fake`
AI_PROVIDER (backend/.env.test), which deterministically echoes the last
user message and reports `grounded` from whether grounding data was built.
"""

import pytest

pytestmark = pytest.mark.anyio


async def _signup_and_get_token(client, email="assistant-contract@example.com"):
    r = await client.post(
        "/auth/signup", json={"email": email, "password": "correct horse battery staple", "name": "Assistant Test"}
    )
    body = r.json()
    return body["access_token"], body["organization"]["id"]


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _create_project(client, token, name="Assistant Project"):
    r = await client.post("/projects", json={"name": name, "url": "https://example.com"}, headers=_auth_headers(token))
    return r.json()["id"]


async def test_chat_requires_authentication(client):
    response = await client.post("/assistant/chat", json={"message": "hello"})
    assert response.status_code == 401


async def test_chat_without_a_project_succeeds_and_is_not_grounded(client):
    token, _ = await _signup_and_get_token(client)

    response = await client.post("/assistant/chat", json={"message": "What can you help me with?"}, headers=_auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    assert body["conversation_id"]
    assert "What can you help me with?" in body["message"]
    assert body["grounded"] is False


async def test_chat_with_an_authorized_project_succeeds_and_is_grounded(client):
    token, _ = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)

    response = await client.post(
        "/assistant/chat",
        json={"message": "What are the most important test cases?", "project_id": project_id},
        headers=_auth_headers(token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["grounded"] is True
    assert body["conversation_id"]


async def test_chat_with_a_nonexistent_project_returns_404(client):
    token, _ = await _signup_and_get_token(client)

    response = await client.post(
        "/assistant/chat",
        json={"message": "hello", "project_id": "00000000-0000-0000-0000-000000000000"},
        headers=_auth_headers(token),
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_chat_with_another_organizations_project_returns_404(client):
    """FR-136/SEC-011: cross-tenant access returns 404, never a distinct 403
    that would confirm the project exists."""
    token_a, _ = await _signup_and_get_token(client, email="assistant-org-a@example.com")
    project_id_a = await _create_project(client, token_a)
    token_b, _ = await _signup_and_get_token(client, email="assistant-org-b@example.com")

    response = await client.post(
        "/assistant/chat",
        json={"message": "hello", "project_id": project_id_a},
        headers=_auth_headers(token_b),
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_chat_with_an_empty_message_returns_a_validation_error(client):
    token, _ = await _signup_and_get_token(client)

    response = await client.post("/assistant/chat", json={"message": ""}, headers=_auth_headers(token))

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_failed"


async def test_chat_with_a_whitespace_only_message_returns_a_validation_error(client):
    """Pydantic's min_length=1 alone would accept a single space — the
    service layer's own .strip()-then-check catches this (assistant/service.py)."""
    token, _ = await _signup_and_get_token(client)

    response = await client.post("/assistant/chat", json={"message": "   "}, headers=_auth_headers(token))

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_failed"


async def test_chat_with_an_excessively_large_message_returns_a_validation_error(client):
    token, _ = await _signup_and_get_token(client)

    response = await client.post("/assistant/chat", json={"message": "x" * 4001}, headers=_auth_headers(token))

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_failed"


async def test_chat_provider_failure_returns_a_safe_503_not_provider_internals(client, monkeypatch):
    from testpilot.ai_provider.fake import FakeLLMProvider
    from testpilot.api.v1 import assistant as assistant_route

    monkeypatch.setattr(assistant_route, "get_provider", lambda: FakeLLMProvider(fail_mode="timeout"))
    token, _ = await _signup_and_get_token(client)

    response = await client.post("/assistant/chat", json={"message": "hello"}, headers=_auth_headers(token))

    assert response.status_code == 503
    body = response.json()
    assert body["error"]["code"] == "assistant_unavailable"
    # Never leaks provider-internal text into the client-facing message.
    assert "Simulated provider timeout" not in body["error"]["message"]


async def test_chat_continuing_a_conversation_reuses_its_original_project(client):
    """A conversation's project is fixed at creation — a later message in
    the same conversation stays grounded in that project even if the
    request doesn't repeat project_id (assistant/service.py's design)."""
    token, _ = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)

    first = await client.post(
        "/assistant/chat", json={"message": "first message", "project_id": project_id}, headers=_auth_headers(token)
    )
    conversation_id = first.json()["conversation_id"]

    second = await client.post(
        "/assistant/chat",
        json={"message": "second message", "conversation_id": conversation_id},
        headers=_auth_headers(token),
    )

    assert second.status_code == 200
    assert second.json()["grounded"] is True
    assert second.json()["conversation_id"] == conversation_id


async def test_chat_conversation_history_is_isolated_across_users(client):
    """Conversation history is personal — another user (even a fresh
    Organization's own owner) cannot continue someone else's conversation by
    guessing/reusing its id."""
    token_a, _ = await _signup_and_get_token(client, email="assistant-history-a@example.com")
    first = await client.post("/assistant/chat", json={"message": "hello"}, headers=_auth_headers(token_a))
    conversation_id = first.json()["conversation_id"]

    token_b, _ = await _signup_and_get_token(client, email="assistant-history-b@example.com")
    response = await client.post(
        "/assistant/chat",
        json={"message": "hi", "conversation_id": conversation_id},
        headers=_auth_headers(token_b),
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_chat_with_a_nonexistent_conversation_id_returns_404(client):
    token, _ = await _signup_and_get_token(client)

    response = await client.post(
        "/assistant/chat",
        json={"message": "hello", "conversation_id": "00000000-0000-0000-0000-000000000000"},
        headers=_auth_headers(token),
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def _create_test_case(client, token, project_id, title="Login with valid credentials"):
    r = await client.post(
        f"/projects/{project_id}/test-cases",
        json={"title": title, "description": "Verifies login succeeds.", "priority": "high", "severity": "major"},
        headers=_auth_headers(token),
    )
    return r.json()["id"]


async def test_chat_with_a_grounded_project_returns_valid_citations(client):
    """FR-102: the fake provider deterministically cites the first test
    case present in grounding_data — end-to-end proof the citation actually
    reaches the HTTP response with a real, dereferenceable id/title/url."""
    token, _ = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)
    test_case_id = await _create_test_case(client, token, project_id)

    response = await client.post(
        "/assistant/chat",
        json={"message": "What are my most important test cases?", "project_id": project_id},
        headers=_auth_headers(token),
    )

    assert response.status_code == 200
    citations = response.json()["referenced_entities"]
    assert len(citations) == 1
    assert citations[0]["entity_type"] == "test_case"
    assert citations[0]["entity_id"] == test_case_id
    assert citations[0]["title"] == "Login with valid credentials"
    assert citations[0]["url"] == f"/projects/{project_id}/test-cases/{test_case_id}"


async def test_chat_without_a_project_returns_no_citations(client):
    token, _ = await _signup_and_get_token(client)

    response = await client.post("/assistant/chat", json={"message": "What's a good QA strategy?"}, headers=_auth_headers(token))

    assert response.status_code == 200
    assert response.json()["referenced_entities"] == []


async def test_chat_never_returns_a_citation_to_another_organizations_entity(client, monkeypatch):
    """Simulates a compromised/hallucinating provider that always claims a
    citation to a real entity from a DIFFERENT Organization's project —
    proves server-side validation (not just "the model wouldn't do that")
    is what keeps this out of the response."""
    from testpilot.ai_provider.base import ChatCitation, ChatContext, ChatResponse
    from testpilot.api.v1 import assistant as assistant_route

    token_a, _ = await _signup_and_get_token(client, email="assistant-citation-org-a@example.com")
    other_org_project_id = await _create_project(client, token_a)
    other_org_test_case_id = await _create_test_case(client, token_a, other_org_project_id)

    class _MaliciousProvider:
        provider_name = "malicious"
        model = "malicious"

        async def chat(self, context: ChatContext) -> ChatResponse:
            return ChatResponse(
                message="Here's an answer.",
                grounded=context.grounding_data is not None,
                referenced_entities=[ChatCitation(entity_type="test_case", entity_id=other_org_test_case_id)],
            )

    monkeypatch.setattr(assistant_route, "get_provider", lambda: _MaliciousProvider())

    token_b, _ = await _signup_and_get_token(client, email="assistant-citation-org-b@example.com")
    project_id_b = await _create_project(client, token_b)
    await _create_test_case(client, token_b, project_id_b, title="Org B's own test case")

    response = await client.post(
        "/assistant/chat",
        json={"message": "What should I test?", "project_id": project_id_b},
        headers=_auth_headers(token_b),
    )

    assert response.status_code == 200
    assert response.json()["referenced_entities"] == []


async def test_chat_citations_never_expose_project_settings(client):
    token, _ = await _signup_and_get_token(client)
    r = await client.post(
        "/projects",
        json={"name": "Secret Project", "url": "https://example.com", "settings": {"api_key": "sk-should-never-leak"}},
        headers=_auth_headers(token),
    )
    project_id = r.json()["id"]
    await _create_test_case(client, token, project_id)

    response = await client.post(
        "/assistant/chat",
        json={"message": "What should I test?", "project_id": project_id},
        headers=_auth_headers(token),
    )

    assert response.status_code == 200
    assert "sk-should-never-leak" not in response.text
