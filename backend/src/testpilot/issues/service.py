"""Issues business logic (contracts/issues-api.md, FR-087-FR-096, T170).

Reads `execution`'s models directly (`TestResult`/`TestRun`, and `execution.
artifact_models.Artifact`) the same way `ai_analysis`/`ai_generation` read
other libraries' models — this library orchestrates across them rather than
duplicating their schema.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from testpilot.core.db import session_scope
from testpilot.core.exceptions import NotFoundError, ValidationFailedError
from testpilot.execution.artifact_models import Artifact
from testpilot.execution.models import TestResult, TestRun
from testpilot.issues.models import (
    Issue,
    IssueAttachment,
    IssueAttachmentType,
    IssuePriority,
    IssueSeverity,
    IssueStatus,
)
from testpilot.projects.models import Project
from testpilot.storage.base import ArtifactStorage
from testpilot.testcases.models import TestCase

_ARTIFACT_URL_EXPIRES_IN_SECONDS = 300
_ALLOWED_UPLOAD_CONTENT_TYPES = {"image/png", "image/jpeg", "image/gif", "text/plain"}
_MAX_ATTACHMENT_SIZE_BYTES = 5 * 1024 * 1024

# contracts/issues-api.md's status lifecycle: from any non-terminal status
# (open/in_progress/resolved) every transition is valid; a terminal status
# (closed/wont_fix) may only transition back to `open`, never directly to
# another non-open status.
_TERMINAL_STATUSES = {IssueStatus.closed, IssueStatus.wont_fix}


class ResultNotFoundError(NotFoundError):
    code = "result_not_found"


class InvalidStatusTransitionError(ValidationFailedError):
    code = "invalid_status_transition"


class InvalidFileTypeError(ValidationFailedError):
    code = "invalid_file_type"


class FileTooLargeError(ValidationFailedError):
    code = "file_too_large"


def _validate_status_transition(current: IssueStatus, new: IssueStatus) -> None:
    if current == new:
        return
    if current in _TERMINAL_STATUSES and new != IssueStatus.open:
        raise InvalidStatusTransitionError(
            f"Cannot transition an issue from {current.value!r} to {new.value!r} — re-open it first",
            details={"from": current.value, "to": new.value},
        )


async def _get_project_or_404(session: AsyncSession, *, organization_id: uuid.UUID, project_id: uuid.UUID) -> Project:
    result = await session.execute(
        select(Project).where(Project.id == project_id, Project.organization_id == organization_id)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise NotFoundError("Project not found")
    return project


async def _get_issue_or_404(
    session: AsyncSession, *, organization_id: uuid.UUID, project_id: uuid.UUID, issue_id: uuid.UUID
) -> Issue:
    result = await session.execute(
        select(Issue).where(
            Issue.id == issue_id, Issue.project_id == project_id, Issue.organization_id == organization_id
        )
    )
    issue = result.scalar_one_or_none()
    if issue is None:
        raise NotFoundError("Issue not found")
    return issue


async def _get_result_for_project_or_404(
    session: AsyncSession, *, organization_id: uuid.UUID, project_id: uuid.UUID, result_id: uuid.UUID
) -> TestResult:
    result = await session.execute(
        select(TestResult).where(TestResult.id == result_id, TestResult.organization_id == organization_id)
    )
    test_result = result.scalar_one_or_none()
    if test_result is None:
        raise ResultNotFoundError("Test result not found")

    run_result = await session.execute(
        select(TestRun).where(
            TestRun.id == test_result.test_run_id, TestRun.project_id == project_id, TestRun.organization_id == organization_id
        )
    )
    if run_result.scalar_one_or_none() is None:
        raise ResultNotFoundError("Test result not found")
    return test_result


async def create_issue(
    *,
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
    created_by_user_id: uuid.UUID,
    title: str,
    description: str,
    severity: IssueSeverity,
    priority: IssuePriority,
) -> Issue:
    """FR-088: manual creation, independent of any test result."""
    async with session_scope(organization_id=str(organization_id)) as session:
        await _get_project_or_404(session, organization_id=organization_id, project_id=project_id)

        issue = Issue(
            organization_id=organization_id,
            project_id=project_id,
            title=title,
            description=description,
            severity=severity,
            priority=priority,
            status=IssueStatus.open,
            created_by_user_id=created_by_user_id,
        )
        session.add(issue)
        await session.flush()
        await session.refresh(issue)
        return issue


async def create_issue_from_result(
    *,
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
    result_id: uuid.UUID,
    created_by_user_id: uuid.UUID,
    title: str | None,
    description: str | None,
    severity: IssueSeverity,
    priority: IssuePriority,
) -> Issue:
    """FR-087/FR-091: pre-filled from the failure, pre-linked to its source
    test case and run; FR-092/T168: the failure's captured screenshots/logs
    are copied as attachment references (same storage_key, no re-upload)."""
    async with session_scope(organization_id=str(organization_id)) as session:
        test_result = await _get_result_for_project_or_404(
            session, organization_id=organization_id, project_id=project_id, result_id=result_id
        )

        case_result = await session.execute(
            select(TestCase).where(TestCase.id == test_result.test_case_id, TestCase.organization_id == organization_id)
        )
        test_case = case_result.scalar_one_or_none()

        final_title = title or (f"{test_case.title} failed" if test_case else "Test failed")
        final_description = description or test_result.error_message or "The test did not produce the expected result."

        issue = Issue(
            organization_id=organization_id,
            project_id=project_id,
            title=final_title,
            description=final_description,
            severity=severity,
            priority=priority,
            status=IssueStatus.open,
            source_test_case_id=test_result.test_case_id,
            source_test_run_id=test_result.test_run_id,
            created_by_user_id=created_by_user_id,
        )
        session.add(issue)
        await session.flush()

        artifacts_result = await session.execute(
            select(Artifact).where(Artifact.test_result_id == result_id, Artifact.storage_key.is_not(None))
        )
        for artifact in artifacts_result.scalars().all():
            session.add(
                IssueAttachment(
                    organization_id=organization_id,
                    issue_id=issue.id,
                    type=IssueAttachmentType(artifact.type.value),
                    storage_key=artifact.storage_key,
                )
            )

        await session.flush()
        await session.refresh(issue)
        return issue


async def list_issues(
    *,
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
    status: IssueStatus | None = None,
    severity: IssueSeverity | None = None,
    priority: IssuePriority | None = None,
) -> list[Issue]:
    async with session_scope(organization_id=str(organization_id)) as session:
        await _get_project_or_404(session, organization_id=organization_id, project_id=project_id)

        query = select(Issue).where(Issue.project_id == project_id, Issue.organization_id == organization_id)
        if status is not None:
            query = query.where(Issue.status == status)
        if severity is not None:
            query = query.where(Issue.severity == severity)
        if priority is not None:
            query = query.where(Issue.priority == priority)
        query = query.order_by(Issue.created_at.desc())

        result = await session.execute(query)
        return list(result.scalars().all())


async def get_issue(
    *, organization_id: uuid.UUID, project_id: uuid.UUID, issue_id: uuid.UUID, storage: ArtifactStorage
) -> tuple[Issue, list[tuple[IssueAttachment, str | None]], TestCase | None, TestRun | None]:
    async with session_scope(organization_id=str(organization_id)) as session:
        issue = await _get_issue_or_404(session, organization_id=organization_id, project_id=project_id, issue_id=issue_id)

        attachments_result = await session.execute(
            select(IssueAttachment).where(IssueAttachment.issue_id == issue_id).order_by(IssueAttachment.created_at)
        )
        attachments = list(attachments_result.scalars().all())

        test_case: TestCase | None = None
        if issue.source_test_case_id is not None:
            case_result = await session.execute(
                select(TestCase).where(TestCase.id == issue.source_test_case_id, TestCase.organization_id == organization_id)
            )
            test_case = case_result.scalar_one_or_none()

        test_run: TestRun | None = None
        if issue.source_test_run_id is not None:
            run_result = await session.execute(
                select(TestRun).where(TestRun.id == issue.source_test_run_id, TestRun.organization_id == organization_id)
            )
            test_run = run_result.scalar_one_or_none()

    attachments_with_urls: list[tuple[IssueAttachment, str | None]] = []
    for attachment in attachments:
        try:
            url = await storage.get_url(attachment.storage_key, expires_in=_ARTIFACT_URL_EXPIRES_IN_SECONDS)
        except Exception:  # noqa: BLE001 — a storage hiccup must not 500 the whole issue view
            url = None
        attachments_with_urls.append((attachment, url))

    return issue, attachments_with_urls, test_case, test_run


async def update_issue(
    *, organization_id: uuid.UUID, project_id: uuid.UUID, issue_id: uuid.UUID, updates: dict[str, Any]
) -> Issue:
    async with session_scope(organization_id=str(organization_id)) as session:
        issue = await _get_issue_or_404(session, organization_id=organization_id, project_id=project_id, issue_id=issue_id)

        if "status" in updates and updates["status"] is not None:
            _validate_status_transition(issue.status, updates["status"])

        for field, value in updates.items():
            setattr(issue, field, value)
        session.add(issue)

        await session.flush()
        await session.refresh(issue)
        return issue


async def _organization_owns_storage_key(session: AsyncSession, *, organization_id: uuid.UUID, storage_key: str) -> bool:
    """SEC-011: a client-supplied `storage_key` must reference something
    this Organization already owns before we mint it a signed URL — never
    trust an opaque key blindly, which would otherwise let one org
    reference another org's artifact by guessing/observing its key."""
    artifact_result = await session.execute(
        select(Artifact.id).where(Artifact.organization_id == organization_id, Artifact.storage_key == storage_key)
    )
    if artifact_result.scalar_one_or_none() is not None:
        return True
    attachment_result = await session.execute(
        select(IssueAttachment.id).where(
            IssueAttachment.organization_id == organization_id, IssueAttachment.storage_key == storage_key
        )
    )
    return attachment_result.scalar_one_or_none() is not None


async def add_attachment_from_storage_key(
    *,
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
    issue_id: uuid.UUID,
    storage_key: str,
    attachment_type: IssueAttachmentType,
) -> IssueAttachment:
    """FR-092, the "existing artifact" variant of the attachments endpoint."""
    async with session_scope(organization_id=str(organization_id)) as session:
        await _get_issue_or_404(session, organization_id=organization_id, project_id=project_id, issue_id=issue_id)

        if not await _organization_owns_storage_key(session, organization_id=organization_id, storage_key=storage_key):
            raise NotFoundError("No artifact found for the given storage key")

        attachment = IssueAttachment(
            organization_id=organization_id, issue_id=issue_id, type=attachment_type, storage_key=storage_key
        )
        session.add(attachment)
        await session.flush()
        await session.refresh(attachment)
        return attachment


async def add_attachment_from_upload(
    *,
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
    issue_id: uuid.UUID,
    data: bytes,
    content_type: str,
    attachment_type: IssueAttachmentType,
    storage: ArtifactStorage,
) -> IssueAttachment:
    """FR-092, the direct-file-upload variant. SEC-013: validates content
    type against an allow-list and enforces a size ceiling before ever
    touching object storage."""
    if content_type not in _ALLOWED_UPLOAD_CONTENT_TYPES:
        raise InvalidFileTypeError(f"Unsupported file type: {content_type!r}")
    if len(data) > _MAX_ATTACHMENT_SIZE_BYTES:
        raise FileTooLargeError("Attachment exceeds the maximum allowed size")

    async with session_scope(organization_id=str(organization_id)) as session:
        await _get_issue_or_404(session, organization_id=organization_id, project_id=project_id, issue_id=issue_id)

    storage_key = await storage.put(data, content_type)

    async with session_scope(organization_id=str(organization_id)) as session:
        attachment = IssueAttachment(
            organization_id=organization_id, issue_id=issue_id, type=attachment_type, storage_key=storage_key
        )
        session.add(attachment)
        await session.flush()
        await session.refresh(attachment)
        return attachment
