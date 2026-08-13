"""Request/response schemas for the Issues API (contracts/issues-api.md)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from testpilot.issues.models import IssueAttachmentType, IssuePriority, IssueSeverity, IssueStatus


class CreateIssueRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(min_length=1)
    severity: IssueSeverity
    priority: IssuePriority


class CreateIssueFromResultRequest(BaseModel):
    """`title`/`description` default from the failure when omitted (FR-087)."""

    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = Field(default=None, min_length=1)
    severity: IssueSeverity
    priority: IssuePriority


class UpdateIssueRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = Field(default=None, min_length=1)
    severity: IssueSeverity | None = None
    priority: IssuePriority | None = None
    status: IssueStatus | None = None
    assignee_user_id: uuid.UUID | None = None


class AddAttachmentFromStorageKeyRequest(BaseModel):
    storage_key: str
    type: IssueAttachmentType


class IssuePublic(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    title: str
    description: str
    severity: IssueSeverity
    priority: IssuePriority
    status: IssueStatus
    assignee_user_id: uuid.UUID | None
    source_test_case_id: uuid.UUID | None
    source_test_run_id: uuid.UUID | None
    created_by_user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class IssueAttachmentPublic(BaseModel):
    id: uuid.UUID
    type: IssueAttachmentType
    # `_storage-note` (contracts/_conventions.md): a short-lived signed URL,
    # never a permanent public link or raw storage_key/credential.
    url: str | None
    created_at: datetime


class IssueListResponse(BaseModel):
    items: list[IssuePublic]


class TestCaseRefPublic(BaseModel):
    id: uuid.UUID
    title: str


class TestRunRefPublic(BaseModel):
    id: uuid.UUID
    status: str


class IssueDetailResponse(BaseModel):
    issue: IssuePublic
    attachments: list[IssueAttachmentPublic]
    # `None` when the issue has no source (a manually created issue) or the
    # source row has since been hard-deleted (SET NULL — FR-096's own
    # documented exception to "the link survives").
    source_test_case: TestCaseRefPublic | None
    source_test_run: TestRunRefPublic | None
