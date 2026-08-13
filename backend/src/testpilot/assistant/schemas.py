import uuid

from pydantic import BaseModel


class ChatRequest(BaseModel):
    """Future scope (FR-097-FR-103) — the route accepting this body is a 501
    stub until the AI QA Assistant ships; the shape is fixed now so the
    eventual implementation is a drop-in, not a breaking API change."""

    message: str
    conversation_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None
