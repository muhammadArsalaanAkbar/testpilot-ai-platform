"""Test cases business logic (contracts/test-cases-api.md, FR-041-FR-057).

AI generation (FR-036-FR-047, the `/generate` family of endpoints) is
Phase 9's ai_generation library, which will call into this module's CRUD
rather than duplicate it (generated cases are just TestCase rows with
source=ai_generated) — nothing generation-specific lives here yet.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from testpilot.audit import service as audit
from testpilot.core.db import session_scope
from testpilot.core.exceptions import NotFoundError, ProjectArchivedError
from testpilot.projects.models import Project, ProjectStatus
from testpilot.testcases.models import (
    TestCase,
    TestCasePriority,
    TestCaseSeverity,
    TestCaseSource,
    TestCaseStatus,
    TestStep,
    TestStepActionType,
)

_SORT_COLUMNS = {
    "priority": TestCase.priority,
    "severity": TestCase.severity,
    "status": TestCase.status,
    "updated_at": TestCase.updated_at,
}


@dataclass
class StepInput:
    action_type: TestStepActionType
    target_descriptor: str | None = None
    input_value: str | None = None
    expected_assertion: str | None = None
    order_index: int | None = None
    capture_screenshot: bool = False


async def _get_project_or_404(session: AsyncSession, *, organization_id: uuid.UUID, project_id: uuid.UUID) -> Project:
    result = await session.execute(
        select(Project).where(Project.id == project_id, Project.organization_id == organization_id)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise NotFoundError("Project not found")
    return project


async def _get_test_case_or_404(
    session: AsyncSession, *, organization_id: uuid.UUID, project_id: uuid.UUID, test_case_id: uuid.UUID
) -> TestCase:
    result = await session.execute(
        select(TestCase).where(
            TestCase.id == test_case_id,
            TestCase.project_id == project_id,
            TestCase.organization_id == organization_id,
        )
    )
    test_case = result.scalar_one_or_none()
    if test_case is None:
        raise NotFoundError("Test case not found")
    return test_case


async def _steps_for(session: AsyncSession, *, test_case_id: uuid.UUID) -> list[TestStep]:
    result = await session.execute(
        select(TestStep).where(TestStep.test_case_id == test_case_id).order_by(TestStep.order_index)
    )
    return list(result.scalars().all())


async def list_test_cases(
    *,
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
    status: TestCaseStatus | None = None,
    priority: TestCasePriority | None = None,
    severity: TestCaseSeverity | None = None,
    tag: str | None = None,
    source: TestCaseSource | None = None,
    q: str | None = None,
    sort: str | None = None,
    offset: int = 0,
    limit: int = 25,
) -> list[TestCase]:
    async with session_scope(organization_id=str(organization_id)) as session:
        await _get_project_or_404(session, organization_id=organization_id, project_id=project_id)

        query = select(TestCase).where(
            TestCase.project_id == project_id, TestCase.organization_id == organization_id
        )
        if status is not None:
            query = query.where(TestCase.status == status)
        if priority is not None:
            query = query.where(TestCase.priority == priority)
        if severity is not None:
            query = query.where(TestCase.severity == severity)
        if source is not None:
            query = query.where(TestCase.source == source)
        if tag is not None:
            query = query.where(TestCase.tags.contains([tag]))
        if q:
            query = query.where(text("search_vector @@ websearch_to_tsquery('english', :q)").bindparams(q=q))

        sort_value = sort or "-updated_at"
        descending = sort_value.startswith("-")
        sort_key = sort_value[1:] if descending else sort_value
        column = _SORT_COLUMNS.get(sort_key, TestCase.updated_at)
        query = query.order_by(column.desc() if descending else column.asc())
        query = query.offset(offset).limit(limit)

        result = await session.execute(query)
        return list(result.scalars().all())


async def get_test_case(
    *, organization_id: uuid.UUID, project_id: uuid.UUID, test_case_id: uuid.UUID
) -> tuple[TestCase, list[TestStep]]:
    async with session_scope(organization_id=str(organization_id)) as session:
        test_case = await _get_test_case_or_404(
            session, organization_id=organization_id, project_id=project_id, test_case_id=test_case_id
        )
        steps = await _steps_for(session, test_case_id=test_case.id)
        return test_case, steps


async def create_test_case(
    *,
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
    title: str,
    description: str,
    priority: TestCasePriority,
    severity: TestCaseSeverity,
    tags: list[str] | None = None,
    steps: list[StepInput] | None = None,
    source: TestCaseSource = TestCaseSource.manual,
) -> tuple[TestCase, list[TestStep]]:
    async with session_scope(organization_id=str(organization_id)) as session:
        project = await _get_project_or_404(session, organization_id=organization_id, project_id=project_id)
        if project.status == ProjectStatus.archived:
            raise ProjectArchivedError("Cannot create a test case in an archived project")

        test_case = TestCase(
            organization_id=organization_id,
            project_id=project_id,
            title=title,
            description=description,
            priority=priority,
            severity=severity,
            source=source,
            tags=tags or [],
        )
        session.add(test_case)
        await session.flush()

        step_rows = [
            TestStep(
                organization_id=organization_id,
                test_case_id=test_case.id,
                order_index=step.order_index if step.order_index is not None else index,
                action_type=step.action_type,
                target_descriptor=step.target_descriptor,
                input_value=step.input_value,
                expected_assertion=step.expected_assertion,
                capture_screenshot=step.capture_screenshot,
            )
            for index, step in enumerate(steps or [])
        ]
        session.add_all(step_rows)

        await session.flush()
        await session.refresh(test_case)
        for step_row in step_rows:
            await session.refresh(step_row)
        return test_case, step_rows


async def update_test_case(
    *,
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
    test_case_id: uuid.UUID,
    title: str | None = None,
    description: str | None = None,
    priority: TestCasePriority | None = None,
    severity: TestCaseSeverity | None = None,
    tags: list[str] | None = None,
    steps: list[StepInput] | None = None,
) -> tuple[TestCase, list[TestStep]]:
    """FR-041: any field of a test case (AI-generated or manual) can be
    edited before or after approval — provenance (`source`) is preserved
    through edits since it's never one of the updatable fields here."""
    async with session_scope(organization_id=str(organization_id)) as session:
        test_case = await _get_test_case_or_404(
            session, organization_id=organization_id, project_id=project_id, test_case_id=test_case_id
        )

        if title is not None:
            test_case.title = title
        if description is not None:
            test_case.description = description
        if priority is not None:
            test_case.priority = priority
        if severity is not None:
            test_case.severity = severity
        if tags is not None:
            test_case.tags = tags
        session.add(test_case)

        if steps is not None:
            existing_steps = await _steps_for(session, test_case_id=test_case_id)
            for existing in existing_steps:
                await session.delete(existing)
            await session.flush()

            new_steps = [
                TestStep(
                    organization_id=organization_id,
                    test_case_id=test_case_id,
                    order_index=step.order_index if step.order_index is not None else index,
                    action_type=step.action_type,
                    target_descriptor=step.target_descriptor,
                    input_value=step.input_value,
                    expected_assertion=step.expected_assertion,
                    capture_screenshot=step.capture_screenshot,
                )
                for index, step in enumerate(steps)
            ]
            session.add_all(new_steps)

        await session.flush()
        await session.refresh(test_case)
        result_steps = await _steps_for(session, test_case_id=test_case_id)
        return test_case, result_steps


async def _set_status(
    *, organization_id: uuid.UUID, project_id: uuid.UUID, test_case_id: uuid.UUID, status: TestCaseStatus
) -> TestCase:
    async with session_scope(organization_id=str(organization_id)) as session:
        test_case = await _get_test_case_or_404(
            session, organization_id=organization_id, project_id=project_id, test_case_id=test_case_id
        )
        test_case.status = status
        session.add(test_case)
        await session.flush()
        await session.refresh(test_case)
        return test_case


async def approve_test_case(*, organization_id: uuid.UUID, project_id: uuid.UUID, test_case_id: uuid.UUID) -> TestCase:
    return await _set_status(
        organization_id=organization_id,
        project_id=project_id,
        test_case_id=test_case_id,
        status=TestCaseStatus.approved,
    )


async def reject_test_case(*, organization_id: uuid.UUID, project_id: uuid.UUID, test_case_id: uuid.UUID) -> TestCase:
    """FR-042: rejected cases are excluded from execution (enforced by
    Phase 11's run-selection query, FR-057) but retained, not deleted."""
    return await _set_status(
        organization_id=organization_id,
        project_id=project_id,
        test_case_id=test_case_id,
        status=TestCaseStatus.rejected,
    )


async def delete_test_case(
    *, organization_id: uuid.UUID, project_id: uuid.UUID, test_case_id: uuid.UUID, actor_user_id: uuid.UUID
) -> None:
    async with session_scope(organization_id=str(organization_id)) as session:
        test_case = await _get_test_case_or_404(
            session, organization_id=organization_id, project_id=project_id, test_case_id=test_case_id
        )
        await session.delete(test_case)

    await audit.record(
        action="test_case_deleted",
        actor_user_id=actor_user_id,
        organization_id=organization_id,
        resource_type="test_case",
        resource_id=test_case_id,
    )
