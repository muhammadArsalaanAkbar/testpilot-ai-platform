"""Response schema for the generation-run endpoints on the test-cases router
(contracts/test-cases-api.md)."""

import uuid
from datetime import datetime

from pydantic import BaseModel

from testpilot.ai_generation.models import GenerationScope, GenerationStatus


class GenerationRunPublic(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    scope: GenerationScope
    status: GenerationStatus
    failure_reason: str | None
    created_test_case_ids: list[uuid.UUID]
    created_at: datetime
    completed_at: datetime | None
