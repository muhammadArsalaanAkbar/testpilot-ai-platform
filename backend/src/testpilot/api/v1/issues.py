"""Issues routes (contracts/issues-api.md, T171)."""

import json
import uuid

import pydantic
from fastapi import APIRouter, Depends, Query, Request, status
from starlette.datastructures import UploadFile

from testpilot.api.deps import CurrentUser, get_current_user
from testpilot.core.exceptions import ValidationFailedError
from testpilot.execution.models import TestRun
from testpilot.issues import service
from testpilot.issues.models import (
    Issue,
    IssueAttachment,
    IssueAttachmentType,
    IssuePriority,
    IssueSeverity,
    IssueStatus,
)
from testpilot.issues.schemas import (
    AddAttachmentFromStorageKeyRequest,
    CreateIssueFromResultRequest,
    CreateIssueRequest,
    IssueAttachmentPublic,
    IssueDetailResponse,
    IssueListResponse,
    IssuePublic,
    TestCaseRefPublic,
    TestRunRefPublic,
    UpdateIssueRequest,
)
from testpilot.storage import get_storage
from testpilot.testcases.models import TestCase

router = APIRouter(prefix="/projects/{project_id}/issues", tags=["issues"])


def _issue_to_public(issue: Issue) -> IssuePublic:
    return IssuePublic(
        id=issue.id,
        project_id=issue.project_id,
        title=issue.title,
        description=issue.description,
        severity=issue.severity,
        priority=issue.priority,
        status=issue.status,
        assignee_user_id=issue.assignee_user_id,
        source_test_case_id=issue.source_test_case_id,
        source_test_run_id=issue.source_test_run_id,
        created_by_user_id=issue.created_by_user_id,
        created_at=issue.created_at,
        updated_at=issue.updated_at,
    )


def _attachment_to_public(attachment: IssueAttachment, url: str | None) -> IssueAttachmentPublic:
    return IssueAttachmentPublic(id=attachment.id, type=attachment.type, url=url, created_at=attachment.created_at)


def _test_case_ref(test_case: TestCase | None) -> TestCaseRefPublic | None:
    if test_case is None:
        return None
    return TestCaseRefPublic(id=test_case.id, title=test_case.title)


def _test_run_ref(test_run: TestRun | None) -> TestRunRefPublic | None:
    if test_run is None:
        return None
    return TestRunRefPublic(id=test_run.id, status=test_run.status.value)


@router.get("", response_model=IssueListResponse)
async def list_issues(
    project_id: uuid.UUID,
    status_filter: IssueStatus | None = Query(None, alias="status"),
    severity: IssueSeverity | None = Query(None),
    priority: IssuePriority | None = Query(None),
    current_user: CurrentUser = Depends(get_current_user),
) -> IssueListResponse:
    issues = await service.list_issues(
        organization_id=uuid.UUID(current_user.organization_id),
        project_id=project_id,
        status=status_filter,
        severity=severity,
        priority=priority,
    )
    return IssueListResponse(items=[_issue_to_public(i) for i in issues])


@router.post("", response_model=IssuePublic, status_code=status.HTTP_201_CREATED)
async def create_issue(
    project_id: uuid.UUID, payload: CreateIssueRequest, current_user: CurrentUser = Depends(get_current_user)
) -> IssuePublic:
    issue = await service.create_issue(
        organization_id=uuid.UUID(current_user.organization_id),
        project_id=project_id,
        created_by_user_id=uuid.UUID(current_user.user_id),
        title=payload.title,
        description=payload.description,
        severity=payload.severity,
        priority=payload.priority,
    )
    return _issue_to_public(issue)


@router.post("/from-result/{result_id}", response_model=IssuePublic, status_code=status.HTTP_201_CREATED)
async def create_issue_from_result(
    project_id: uuid.UUID,
    result_id: uuid.UUID,
    payload: CreateIssueFromResultRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> IssuePublic:
    issue = await service.create_issue_from_result(
        organization_id=uuid.UUID(current_user.organization_id),
        project_id=project_id,
        result_id=result_id,
        created_by_user_id=uuid.UUID(current_user.user_id),
        title=payload.title,
        description=payload.description,
        severity=payload.severity,
        priority=payload.priority,
    )
    return _issue_to_public(issue)


@router.get("/{issue_id}", response_model=IssueDetailResponse)
async def get_issue(
    project_id: uuid.UUID, issue_id: uuid.UUID, current_user: CurrentUser = Depends(get_current_user)
) -> IssueDetailResponse:
    issue, attachments_with_urls, test_case, test_run = await service.get_issue(
        organization_id=uuid.UUID(current_user.organization_id),
        project_id=project_id,
        issue_id=issue_id,
        storage=get_storage(),
    )
    return IssueDetailResponse(
        issue=_issue_to_public(issue),
        attachments=[_attachment_to_public(a, url) for a, url in attachments_with_urls],
        source_test_case=_test_case_ref(test_case),
        source_test_run=_test_run_ref(test_run),
    )


@router.patch("/{issue_id}", response_model=IssuePublic)
async def update_issue(
    project_id: uuid.UUID, issue_id: uuid.UUID, payload: UpdateIssueRequest, current_user: CurrentUser = Depends(get_current_user)
) -> IssuePublic:
    updates = payload.model_dump(exclude_unset=True)
    issue = await service.update_issue(
        organization_id=uuid.UUID(current_user.organization_id), project_id=project_id, issue_id=issue_id, updates=updates
    )
    return _issue_to_public(issue)


@router.post("/{issue_id}/attachments", response_model=IssueAttachmentPublic, status_code=status.HTTP_201_CREATED)
async def add_attachment(
    project_id: uuid.UUID, issue_id: uuid.UUID, request: Request, current_user: CurrentUser = Depends(get_current_user)
) -> IssueAttachmentPublic:
    """Accepts either a multipart file upload or a JSON `{storage_key, type}`
    body referencing an existing artifact (contracts/issues-api.md) — the
    two variants share one endpoint, dispatched on the request's own
    Content-Type, since FastAPI/OpenAPI has no single-route way to declare
    both a file body and a JSON body as alternatives."""
    organization_id = uuid.UUID(current_user.organization_id)
    content_type = request.headers.get("content-type", "")

    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        upload = form.get("file")
        type_field = form.get("type")
        if not isinstance(upload, UploadFile) or not isinstance(type_field, str):
            raise ValidationFailedError("A 'file' and 'type' are required for a multipart upload")
        data = await upload.read()
        attachment = await service.add_attachment_from_upload(
            organization_id=organization_id,
            project_id=project_id,
            issue_id=issue_id,
            data=data,
            content_type=upload.content_type or "application/octet-stream",
            attachment_type=IssueAttachmentType(type_field),
            storage=get_storage(),
        )
    else:
        # T206/FR-130: this branch reads the body directly (request.json())
        # rather than through a FastAPI-declared Pydantic parameter — one
        # route can't declare both a file body and a JSON body as
        # alternatives — so it must validate exactly as strictly as a
        # normal declared body would, converting any parse/shape error into
        # the same 422 `validation_failed` envelope instead of letting a
        # raw JSONDecodeError/KeyError/ValueError surface as an
        # unhandled 500.
        try:
            raw_body = await request.json()
            body = AddAttachmentFromStorageKeyRequest.model_validate(raw_body)
        except (json.JSONDecodeError, pydantic.ValidationError) as exc:
            raise ValidationFailedError("Invalid request body") from exc

        attachment = await service.add_attachment_from_storage_key(
            organization_id=organization_id,
            project_id=project_id,
            issue_id=issue_id,
            storage_key=body.storage_key,
            attachment_type=body.type,
        )

    try:
        url = await get_storage().get_url(attachment.storage_key, expires_in=300)
    except Exception:  # noqa: BLE001 — a storage hiccup must not fail the just-created attachment's own response
        url = None
    return _attachment_to_public(attachment, url)
