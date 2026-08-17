"""AI QA Assistant routes (FR-097-FR-103): POST /assistant/chat.

Synchronous, unlike the AI generation/analysis routes — no queue/poll, see
assistant/service.py's module docstring for why."""

import uuid

from fastapi import APIRouter, Depends, Request

from testpilot.ai_provider import get_provider
from testpilot.api.deps import CurrentUser, get_current_user, limiter
from testpilot.assistant import service
from testpilot.assistant.schemas import ChatCitationPublic, ChatRequest, ChatResponse

router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.post("/chat", response_model=ChatResponse)
@limiter.limit("20/minute")
async def chat(
    request: Request, payload: ChatRequest, current_user: CurrentUser = Depends(get_current_user)
) -> ChatResponse:
    result = await service.send_message(
        organization_id=uuid.UUID(current_user.organization_id),
        user_id=uuid.UUID(current_user.user_id),
        message=payload.message,
        conversation_id=payload.conversation_id,
        project_id=payload.project_id,
        provider=get_provider(),
    )
    return ChatResponse(
        conversation_id=result.conversation_id,
        message=result.message,
        grounded=result.grounded,
        referenced_entities=[
            ChatCitationPublic(entity_type=c.entity_type, entity_id=c.entity_id, title=c.title, url=c.url)
            for c in result.referenced_entities
        ],
    )
