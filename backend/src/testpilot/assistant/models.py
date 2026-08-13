"""`assistant_conversations`/`assistant_messages` models (data-model.md
Future-Only Schema, T177, FR-097-FR-103).

Shipped ahead of the `assistant` library itself so retaining conversation
history later needs no interface-breaking migration, mirroring
contracts/ai-provider-adapter.md's rationale for declaring `LLMProvider.chat`
on the Protocol early. These tables are inert until a future phase wires
real persistence to them — see api/v1/assistant.py's 501 stub.
"""

import uuid
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import Column, ForeignKey, Index
from sqlalchemy import Uuid as SAUuid
from sqlmodel import Field, SQLModel

from testpilot.core.models import IDMixin, OrgScopedMixin, tz_datetime_field


def _utcnow() -> datetime:
    return datetime.now(UTC)


class AssistantMessageRole(StrEnum):
    user = "user"
    assistant = "assistant"


class AssistantConversation(IDMixin, OrgScopedMixin, SQLModel, table=True):
    __tablename__ = "assistant_conversations"
    __table_args__ = (Index("ix_assistant_conversations_organization_id_user_id", "organization_id", "user_id"),)

    user_id: uuid.UUID = Field(foreign_key="users.id", nullable=False, index=True)
    # SET NULL (not CASCADE): FR-101 requires retaining a user's conversation
    # history even after the project it happened to reference is deleted —
    # same rationale as Issue.source_test_case_id/source_test_run_id.
    project_id: uuid.UUID | None = Field(
        default=None, sa_column=Column(SAUuid, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    )
    created_at: datetime = tz_datetime_field(nullable=False, default_factory=_utcnow)


class AssistantMessage(IDMixin, OrgScopedMixin, SQLModel, table=True):
    __tablename__ = "assistant_messages"
    __table_args__ = (Index("ix_assistant_messages_conversation_id", "conversation_id"),)

    conversation_id: uuid.UUID = Field(
        sa_column=Column(
            SAUuid, ForeignKey("assistant_conversations.id", ondelete="CASCADE"), nullable=False, index=True
        )
    )
    role: AssistantMessageRole = Field(nullable=False)
    content: str = Field(nullable=False)
    created_at: datetime = tz_datetime_field(nullable=False, default_factory=_utcnow)
