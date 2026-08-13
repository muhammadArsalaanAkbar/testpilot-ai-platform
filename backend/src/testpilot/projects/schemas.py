"""Request/response schemas for the Projects API (contracts/projects-api.md)."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from testpilot.projects.models import ProjectStatus


class ProjectPublic(BaseModel):
    id: uuid.UUID
    name: str
    url: str
    status: ProjectStatus
    settings: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class ProjectsListResponse(BaseModel):
    items: list[ProjectPublic]


class CreateProjectRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    url: str = Field(min_length=1)
    settings: dict[str, Any] | None = None


class UpdateProjectRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    url: str | None = Field(default=None, min_length=1)
    settings: dict[str, Any] | None = None


class DeleteProjectRequest(BaseModel):
    confirm: bool = False


class ProjectDetailResponse(BaseModel):
    project: ProjectPublic
    # Populated once test runs exist (Phase 11); an empty list is the
    # correct MVP-so-far value, not a placeholder.
    recent_runs: list[Any] = []
