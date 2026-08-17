import uuid

from pydantic import BaseModel, Field

from testpilot.ai_provider.base import CitableEntityType
from testpilot.assistant.service import MAX_MESSAGE_LENGTH


class ChatRequest(BaseModel):
    """POST /assistant/chat request body (FR-097-FR-103). `project_id` is
    optional — omitted for a general, non-project-scoped question; when a
    `conversation_id` is also given, `project_id` is ignored in favor of
    that conversation's own stored project (assistant/service.py)."""

    message: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)
    conversation_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None


class ChatCitationPublic(BaseModel):
    """A server-validated reference to a project entity the answer is
    grounded in (FR-102). `title`/`url` are resolved server-side from data
    already scoped to the requesting user's Organization — never taken
    verbatim from the model's own output (assistant/service.py's
    `_resolve_citations`)."""

    entity_type: CitableEntityType
    entity_id: uuid.UUID
    title: str
    url: str


class ChatResponse(BaseModel):
    conversation_id: uuid.UUID
    message: str
    grounded: bool
    referenced_entities: list[ChatCitationPublic]
