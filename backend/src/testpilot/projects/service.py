"""Projects business logic (contracts/projects-api.md, FR-025-FR-035)."""

import uuid
from typing import Any

from sqlalchemy import func, select

from testpilot.audit import service as audit
from testpilot.billing import service as billing_service
from testpilot.core import cache
from testpilot.core.db import session_scope
from testpilot.core.exceptions import ConfirmationRequiredError, NotFoundError
from testpilot.projects.models import Project, ProjectStatus
from testpilot.projects.url_validation import validate_public_url

_PROJECT_CACHE_NAMESPACE = "project"


def _project_cache_key(*, organization_id: uuid.UUID, project_id: uuid.UUID) -> str:
    # Compound key (not project_id alone): a cache lookup bypasses the DB's
    # own `WHERE organization_id = ...` filter entirely, so the key itself
    # — not a check performed after the fact — is what has to enforce
    # tenant isolation here (FR-136/SEC-011), the same guarantee
    # `get_project`'s own query provides.
    return f"{organization_id}:{project_id}"


async def _active_project_count(*, organization_id: uuid.UUID) -> int:
    async with session_scope(organization_id=str(organization_id)) as session:
        result = await session.execute(
            select(func.count())
            .select_from(Project)
            .where(Project.organization_id == organization_id, Project.status == ProjectStatus.active)
        )
        return result.scalar_one()


async def list_projects(*, organization_id: uuid.UUID, status: ProjectStatus | None = None) -> list[Project]:
    async with session_scope(organization_id=str(organization_id)) as session:
        query = select(Project).where(Project.organization_id == organization_id)
        if status is not None:
            query = query.where(Project.status == status)
        query = query.order_by(Project.created_at.desc())
        result = await session.execute(query)
        return list(result.scalars().all())


async def get_project(*, organization_id: uuid.UUID, project_id: uuid.UUID) -> Project:
    """`organization_id` MUST come only from the authenticated user's own
    session claims — filtering by it here (not just `project_id`) is what
    turns a cross-tenant lookup into the same 404 as a nonexistent id
    (FR-136/SEC-011). NFR-008: cached (project metadata is exactly the
    "frequently read, rarely changed" data that requirement names) —
    invalidated explicitly by every write path below on that same
    compound key."""

    async def _load() -> Project | None:
        async with session_scope(organization_id=str(organization_id)) as session:
            result = await session.execute(
                select(Project).where(Project.id == project_id, Project.organization_id == organization_id)
            )
            return result.scalar_one_or_none()

    project = await cache.get_or_set_model(
        namespace=_PROJECT_CACHE_NAMESPACE,
        key=_project_cache_key(organization_id=organization_id, project_id=project_id),
        model_cls=Project,
        loader=_load,
    )
    if project is None:
        raise NotFoundError("Project not found")
    return project


async def create_project(
    *, organization_id: uuid.UUID, name: str, url: str, settings: dict[str, Any] | None = None
) -> Project:
    await validate_public_url(url)

    # Archived projects don't count toward the limit (FR-028: archiving is
    # the user's way to free up a slot while keeping history — if it still
    # counted, archiving would never relieve the limit and only delete
    # would, defeating the point of the two being distinct actions).
    current_active = await _active_project_count(organization_id=organization_id)
    await billing_service.check_count_limit(
        organization_id=organization_id, metric="projects", prospective_count=current_active + 1
    )

    async with session_scope(organization_id=str(organization_id)) as session:
        project = Project(organization_id=organization_id, name=name, url=url, settings=settings or {})
        session.add(project)
        await session.flush()
        await session.refresh(project)

    await billing_service.set_count_usage(
        organization_id=organization_id, metric="projects", count=current_active + 1
    )
    return project


async def update_project(
    *,
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
    name: str | None = None,
    url: str | None = None,
    settings: dict[str, Any] | None = None,
) -> Project:
    if url is not None:
        await validate_public_url(url)

    async with session_scope(organization_id=str(organization_id)) as session:
        result = await session.execute(
            select(Project).where(Project.id == project_id, Project.organization_id == organization_id)
        )
        project = result.scalar_one_or_none()
        if project is None:
            raise NotFoundError("Project not found")

        if name is not None:
            project.name = name
        if url is not None:
            project.url = url
        if settings is not None:
            project.settings = settings

        session.add(project)
        await session.flush()
        await session.refresh(project)

    await cache.invalidate(
        namespace=_PROJECT_CACHE_NAMESPACE,
        key=_project_cache_key(organization_id=organization_id, project_id=project_id),
    )
    return project


async def _set_status(*, organization_id: uuid.UUID, project_id: uuid.UUID, status: ProjectStatus) -> Project:
    async with session_scope(organization_id=str(organization_id)) as session:
        result = await session.execute(
            select(Project).where(Project.id == project_id, Project.organization_id == organization_id)
        )
        project = result.scalar_one_or_none()
        if project is None:
            raise NotFoundError("Project not found")

        project.status = status
        session.add(project)
        await session.flush()
        await session.refresh(project)

    await cache.invalidate(
        namespace=_PROJECT_CACHE_NAMESPACE,
        key=_project_cache_key(organization_id=organization_id, project_id=project_id),
    )
    return project


async def archive_project(*, organization_id: uuid.UUID, project_id: uuid.UUID) -> Project:
    """Idempotent (contracts/projects-api.md): archiving an already-archived
    project is a no-op 200, not an error."""
    project = await _set_status(organization_id=organization_id, project_id=project_id, status=ProjectStatus.archived)
    active_count = await _active_project_count(organization_id=organization_id)
    await billing_service.set_count_usage(organization_id=organization_id, metric="projects", count=active_count)
    return project


async def unarchive_project(*, organization_id: uuid.UUID, project_id: uuid.UUID) -> Project:
    current_active = await _active_project_count(organization_id=organization_id)
    await billing_service.check_count_limit(
        organization_id=organization_id, metric="projects", prospective_count=current_active + 1
    )
    project = await _set_status(organization_id=organization_id, project_id=project_id, status=ProjectStatus.active)
    await billing_service.set_count_usage(
        organization_id=organization_id, metric="projects", count=current_active + 1
    )
    return project


async def delete_project(
    *, organization_id: uuid.UUID, project_id: uuid.UUID, confirm: bool, actor_user_id: uuid.UUID
) -> None:
    """Hard delete (FR-029). Cascading delete of test cases/runs/results/
    artifacts (DATA-005) is enforced at the DB level via `ON DELETE CASCADE`
    foreign keys on those tables once Phase 8+ creates them referencing
    `projects.id` — nothing to do here yet since none of those tables exist."""
    if not confirm:
        raise ConfirmationRequiredError("Deleting a project requires explicit confirmation")

    async with session_scope(organization_id=str(organization_id)) as session:
        result = await session.execute(
            select(Project).where(Project.id == project_id, Project.organization_id == organization_id)
        )
        project = result.scalar_one_or_none()
        if project is None:
            raise NotFoundError("Project not found")
        was_active = project.status == ProjectStatus.active
        await session.delete(project)

    await cache.invalidate(
        namespace=_PROJECT_CACHE_NAMESPACE,
        key=_project_cache_key(organization_id=organization_id, project_id=project_id),
    )

    # FR-128: "project deletion" is explicitly named as a required audit
    # event (T209) -- recorded after the delete commits, matching every
    # other audit.record call site's own-transaction pattern.
    await audit.record(
        action="project_deleted",
        actor_user_id=actor_user_id,
        organization_id=organization_id,
        resource_type="project",
        resource_id=project_id,
    )

    if was_active:
        active_count = await _active_project_count(organization_id=organization_id)
        await billing_service.set_count_usage(
            organization_id=organization_id, metric="projects", count=active_count
        )
