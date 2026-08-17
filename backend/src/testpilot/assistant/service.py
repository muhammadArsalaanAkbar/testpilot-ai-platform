"""AI QA Assistant chat orchestration (FR-097-FR-103).

Unlike `ai_generation`/`ai_analysis`'s async-job pattern (enqueue -> worker
executes -> notify), chat is synchronous: a single bounded context build
plus one provider call fits comfortably in a normal request/response cycle,
and a conversational UX needs the reply in the same request, not a poll
loop — `worker/queues.py` has no chat queue by design.

A conversation's `project_id` is fixed at creation (set once from the first
message's request) and reused for every later message in that conversation,
never re-read from a later request body — this keeps "which project is this
conversation grounded in" unambiguous rather than letting a client silently
retarget an in-progress conversation to a different project.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from testpilot.ai_provider.base import AIProviderError, ChatContext, ChatMessage, LLMProvider
from testpilot.assistant.context_builder import build_project_context
from testpilot.assistant.models import AssistantConversation, AssistantMessage, AssistantMessageRole
from testpilot.billing import service as billing_service
from testpilot.core.db import session_scope
from testpilot.core.exceptions import (
    AssistantUnavailableError,
    NotFoundError,
    ValidationFailedError,
)
from testpilot.projects.models import Project

logger = logging.getLogger(__name__)

# Bounded per the assistant spec's "enforce reasonable message/context
# limits" requirement — deliberately conservative, not provider-tuned.
MAX_MESSAGE_LENGTH = 4000
MAX_HISTORY_MESSAGES = 20
_MAX_ATTEMPTS = 2  # same bounded-retry policy as ai_analysis/service.py


@dataclass(frozen=True)
class AssistantChatResult:
    conversation_id: uuid.UUID
    message: str
    grounded: bool
    referenced_entities: list[str]


async def _get_project_or_404(session: AsyncSession, *, organization_id: uuid.UUID, project_id: uuid.UUID) -> Project:
    result = await session.execute(
        select(Project).where(Project.id == project_id, Project.organization_id == organization_id)
    )
    project = result.scalar_one_or_none()
    if project is None:
        # FR-136/SEC-011: identical response whether the project doesn't
        # exist or belongs to another Organization — never a distinct 403.
        raise NotFoundError("Project not found")
    return project


async def _get_or_create_conversation(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID | None,
    project_id: uuid.UUID | None,
) -> AssistantConversation:
    if conversation_id is None:
        conversation = AssistantConversation(organization_id=organization_id, user_id=user_id, project_id=project_id)
        session.add(conversation)
        await session.flush()
        await session.refresh(conversation)
        return conversation

    # Scoped by organization_id AND user_id: conversation history is
    # personal, never shared across an Organization's other members (same
    # isolation rationale the assistant_conversations
    # organization_id+user_id index documents). A conversation belonging to
    # another user (in-org or cross-org) is indistinguishable from a
    # nonexistent one here, same masking pattern as project lookups.
    result = await session.execute(
        select(AssistantConversation).where(
            AssistantConversation.id == conversation_id,
            AssistantConversation.organization_id == organization_id,
            AssistantConversation.user_id == user_id,
        )
    )
    existing = result.scalar_one_or_none()
    if existing is None:
        raise NotFoundError("Conversation not found")
    return existing


async def _load_history(
    session: AsyncSession, *, organization_id: uuid.UUID, conversation_id: uuid.UUID
) -> list[AssistantMessage]:
    result = await session.execute(
        select(AssistantMessage)
        .where(
            AssistantMessage.organization_id == organization_id,
            AssistantMessage.conversation_id == conversation_id,
        )
        .order_by(AssistantMessage.created_at.desc())
        .limit(MAX_HISTORY_MESSAGES)
    )
    return list(reversed(result.scalars().all()))


async def send_message(
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    message: str,
    conversation_id: uuid.UUID | None,
    project_id: uuid.UUID | None,
    provider: LLMProvider,
) -> AssistantChatResult:
    message = message.strip()
    if not message:
        raise ValidationFailedError("message must not be empty")
    if len(message) > MAX_MESSAGE_LENGTH:
        raise ValidationFailedError(
            f"message must be at most {MAX_MESSAGE_LENGTH} characters",
            details={"max_length": MAX_MESSAGE_LENGTH},
        )

    # FR-123-FR-125: same plan-limit check every other AI operation makes,
    # before any provider call is attempted.
    await billing_service.check_and_reserve_period_usage(organization_id=organization_id, metric="ai_operations")

    async with session_scope(organization_id=str(organization_id)) as session:
        if project_id is not None:
            await _get_project_or_404(session, organization_id=organization_id, project_id=project_id)

        conversation = await _get_or_create_conversation(
            session,
            organization_id=organization_id,
            user_id=user_id,
            conversation_id=conversation_id,
            project_id=project_id,
        )
        history = await _load_history(session, organization_id=organization_id, conversation_id=conversation.id)

        session.add(
            AssistantMessage(
                organization_id=organization_id,
                conversation_id=conversation.id,
                role=AssistantMessageRole.user,
                content=message,
            )
        )

    grounding_data = None
    if conversation.project_id is not None:
        async with session_scope(organization_id=str(organization_id)) as session:
            grounding_data = await build_project_context(
                session, organization_id=organization_id, project_id=conversation.project_id
            )

    chat_messages = [ChatMessage(role=m.role.value, content=m.content) for m in history]
    chat_messages.append(ChatMessage(role="user", content=message))
    context = ChatContext(messages=chat_messages, grounding_data=grounding_data)

    start = time.monotonic()
    response = None
    failure_reason: str | None = None
    for attempt in range(_MAX_ATTEMPTS):
        try:
            response = await provider.chat(context)
            break
        except AIProviderError as exc:
            failure_reason = str(exc)
            if not exc.retryable or attempt == _MAX_ATTEMPTS - 1:
                break
    latency_ms = int((time.monotonic() - start) * 1000)

    if response is None:
        logger.warning(
            "assistant_chat failure conversation_id=%s project_id=%s provider=%s latency_ms=%d reason=%s",
            conversation.id,
            conversation.project_id,
            provider.provider_name,
            latency_ms,
            failure_reason,
        )
        raise AssistantUnavailableError("The AI QA Assistant is temporarily unavailable")

    async with session_scope(organization_id=str(organization_id)) as session:
        session.add(
            AssistantMessage(
                organization_id=organization_id,
                conversation_id=conversation.id,
                role=AssistantMessageRole.assistant,
                content=response.message,
            )
        )

    logger.info(
        "assistant_chat success conversation_id=%s project_id=%s provider=%s grounded=%s latency_ms=%d",
        conversation.id,
        conversation.project_id,
        provider.provider_name,
        response.grounded,
        latency_ms,
    )

    return AssistantChatResult(
        conversation_id=conversation.id,
        message=response.message,
        grounded=response.grounded,
        referenced_entities=response.referenced_entities,
    )
