"""Projects routes (contracts/projects-api.md)."""

import uuid

from fastapi import APIRouter, Depends, Response, status

from testpilot.api.deps import CurrentUser, get_current_user
from testpilot.projects import service
from testpilot.projects.models import Project, ProjectStatus
from testpilot.projects.schemas import (
    CreateProjectRequest,
    DeleteProjectRequest,
    ProjectDetailResponse,
    ProjectPublic,
    ProjectsListResponse,
    UpdateProjectRequest,
)

router = APIRouter(prefix="/projects", tags=["projects"])


def _to_public(project: Project) -> ProjectPublic:
    return ProjectPublic(
        id=project.id,
        name=project.name,
        url=project.url,
        status=project.status,
        settings=project.settings,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


@router.get("", response_model=ProjectsListResponse)
async def list_projects(
    status_filter: ProjectStatus | None = None, current_user: CurrentUser = Depends(get_current_user)
) -> ProjectsListResponse:
    projects = await service.list_projects(
        organization_id=uuid.UUID(current_user.organization_id), status=status_filter
    )
    return ProjectsListResponse(items=[_to_public(p) for p in projects])


@router.post("", response_model=ProjectPublic, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: CreateProjectRequest, current_user: CurrentUser = Depends(get_current_user)
) -> ProjectPublic:
    project = await service.create_project(
        organization_id=uuid.UUID(current_user.organization_id),
        name=payload.name,
        url=payload.url,
        settings=payload.settings,
    )
    return _to_public(project)


@router.get("/{project_id}", response_model=ProjectDetailResponse)
async def get_project(project_id: uuid.UUID, current_user: CurrentUser = Depends(get_current_user)) -> ProjectDetailResponse:
    project = await service.get_project(
        organization_id=uuid.UUID(current_user.organization_id), project_id=project_id
    )
    return ProjectDetailResponse(project=_to_public(project), recent_runs=[])


@router.patch("/{project_id}", response_model=ProjectPublic)
async def update_project(
    project_id: uuid.UUID, payload: UpdateProjectRequest, current_user: CurrentUser = Depends(get_current_user)
) -> ProjectPublic:
    project = await service.update_project(
        organization_id=uuid.UUID(current_user.organization_id),
        project_id=project_id,
        name=payload.name,
        url=payload.url,
        settings=payload.settings,
    )
    return _to_public(project)


@router.post("/{project_id}/archive", response_model=ProjectPublic)
async def archive_project(project_id: uuid.UUID, current_user: CurrentUser = Depends(get_current_user)) -> ProjectPublic:
    project = await service.archive_project(
        organization_id=uuid.UUID(current_user.organization_id), project_id=project_id
    )
    return _to_public(project)


@router.post("/{project_id}/unarchive", response_model=ProjectPublic)
async def unarchive_project(project_id: uuid.UUID, current_user: CurrentUser = Depends(get_current_user)) -> ProjectPublic:
    project = await service.unarchive_project(
        organization_id=uuid.UUID(current_user.organization_id), project_id=project_id
    )
    return _to_public(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: uuid.UUID, payload: DeleteProjectRequest, current_user: CurrentUser = Depends(get_current_user)
) -> Response:
    await service.delete_project(
        organization_id=uuid.UUID(current_user.organization_id),
        project_id=project_id,
        confirm=payload.confirm,
        actor_user_id=uuid.UUID(current_user.user_id),
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
