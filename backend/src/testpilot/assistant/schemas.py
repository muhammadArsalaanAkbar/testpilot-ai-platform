import uuid

from pydantic import BaseModel, Field

from testpilot.assistant.service import MAX_MESSAGE_LENGTH


class ChatRequest(BaseModel):
    """POST /assistant/chat request body (FR-097-FR-103). `project_id` is
    optional — omitted for a general, non-project-scoped question; when a
    `conversation_id` is also given, `project_id` is ignored in favor of
    that conversation's own stored project (assistant/service.py)."""

    message: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)
    conversation_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None


class ChatResponse(BaseModel):
    conversation_id: uuid.UUID
    message: str
    grounded: bool
    referenced_entities: list[str]
