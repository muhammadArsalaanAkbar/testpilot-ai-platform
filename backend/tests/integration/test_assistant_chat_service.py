"""Integration tests for assistant/service.py's orchestration: bounded
provider retry, message durability on provider failure, and conversation
history actually being threaded into subsequent provider calls. Mirrors the
fake-provider-failure-injection pattern tests/integration/test_ai_analysis_failure.py
establishes for ai_analysis/service.py's identical _MAX_ATTEMPTS policy.
"""

import uuid

import pytest
from sqlalchemy import select

from testpilot.ai_provider.base import ChatContext, ChatResponse
from testpilot.ai_provider.fake import FakeLLMProvider
from testpilot.assistant import service as assistant_service
from testpilot.assistant.models import AssistantMessage, AssistantMessageRole
from testpilot.core.db import session_scope
from testpilot.core.exceptions import AssistantUnavailableError

pytestmark = pytest.mark.anyio


async def _signup_and_get_token(client, email="assistant-service@example.com"):
    r = await client.post(
        "/auth/signup", json={"email": email, "password": "correct horse battery staple", "name": "Service Test"}
    )
    body = r.json()
    return body["access_token"], body["organization"]["id"], body["user"]["id"]


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class _CountingProvider(FakeLLMProvider):
    def __init__(self, *, fail_mode: str = "none") -> None:
        super().__init__(fail_mode=fail_mode)
        self.calls = 0

    async def chat(self, context: ChatContext) -> ChatResponse:  # type: ignore[override]
        self.calls += 1
        return await super().chat(context)


async def test_a_retryable_provider_error_is_retried_once_then_fails(client):
    token, organization_id, user_id = await _signup_and_get_token(client)
    provider = _CountingProvider(fail_mode="timeout")

    with pytest.raises(AssistantUnavailableError):
        await assistant_service.send_message(
            organization_id=uuid.UUID(organization_id),
            user_id=uuid.UUID(user_id),
            message="hello",
            conversation_id=None,
            project_id=None,
            provider=provider,
        )

    assert provider.calls == 2


async def test_a_non_retryable_provider_error_fails_immediately_without_retrying(client):
    token, organization_id, user_id = await _signup_and_get_token(client)
    provider = _CountingProvider(fail_mode="malformed")

    with pytest.raises(AssistantUnavailableError):
        await assistant_service.send_message(
            organization_id=uuid.UUID(organization_id),
            user_id=uuid.UUID(user_id),
            message="hello",
            conversation_id=None,
            project_id=None,
            provider=provider,
        )

    assert provider.calls == 1


async def test_the_user_message_is_persisted_even_when_the_provider_fails(client):
    """History durability: a failed AI call must not silently drop the
    user's own message from the conversation record."""
    token, organization_id, user_id = await _signup_and_get_token(client)
    provider = _CountingProvider(fail_mode="malformed")

    with pytest.raises(AssistantUnavailableError):
        await assistant_service.send_message(
            organization_id=uuid.UUID(organization_id),
            user_id=uuid.UUID(user_id),
            message="please don't disappear",
            conversation_id=None,
            project_id=None,
            provider=provider,
        )

    async with session_scope(organization_id=organization_id) as session:
        result = await session.execute(
            select(AssistantMessage).where(AssistantMessage.organization_id == uuid.UUID(organization_id))
        )
        messages = list(result.scalars().all())

    assert len(messages) == 1
    assert messages[0].role == AssistantMessageRole.user
    assert messages[0].content == "please don't disappear"


async def test_conversation_history_is_threaded_into_the_next_provider_call(client):
    token, organization_id, user_id = await _signup_and_get_token(client)
    provider = _CountingProvider()

    first = await assistant_service.send_message(
        organization_id=uuid.UUID(organization_id),
        user_id=uuid.UUID(user_id),
        message="my first message",
        conversation_id=None,
        project_id=None,
        provider=provider,
    )

    captured: dict[str, ChatContext] = {}
    original_chat = provider.chat

    async def _capturing_chat(context: ChatContext) -> ChatResponse:
        captured["context"] = context
        return await original_chat(context)

    provider.chat = _capturing_chat  # type: ignore[method-assign]

    await assistant_service.send_message(
        organization_id=uuid.UUID(organization_id),
        user_id=uuid.UUID(user_id),
        message="my second message",
        conversation_id=first.conversation_id,
        project_id=None,
        provider=provider,
    )

    sent_contents = [m.content for m in captured["context"].messages]
    assert "my first message" in sent_contents
    assert sent_contents[-1] == "my second message"
