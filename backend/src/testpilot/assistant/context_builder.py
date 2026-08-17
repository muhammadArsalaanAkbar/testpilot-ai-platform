"""Bounded, per-entity-capped context assembly for AI QA Assistant chat
(FR-097-FR-103, contracts/ai-provider-adapter.md's `ChatContext.grounding_data`).

Every value included here is Organization/Project-scoped Postgres data —
this module assumes the caller (`assistant/service.py`) has already
established the requesting user is authorized to see `project_id`, and
re-scopes every query by both `organization_id` and `project_id` anyway,
consistent with every other RLS-backed service in this codebase never
relying solely on the caller having checked.

Deliberately excludes:
- `Project.settings` (free-form JSONB with no fixed schema — a project owner
  could store arbitrary config there, and there's no safe way to allowlist
  fields from a dict whose shape this codebase does not constrain), per the
  assistant spec's "never send sensitive infrastructure secrets to the
  model" requirement.
- Artifact binaries — metadata only (DATA-002: type/content_type/size),
  never a fetched screenshot.
- Raw crawled page content — never persisted after a generation job
  completes (see `ai_generation/models.py`), so it is not available to
  ground on here. Documented limitation, not an oversight.

Every string pulled from user/project data (titles, descriptions, error
messages) is inherently untrusted — it can contain text engineered as a
prompt-injection payload. This module does not attempt to sanitize it;
`ai_provider/cloud.py`'s system prompt clearly delimits and labels the whole
context blob as data, never instructions, which is the correct layer for
that guarantee (stripping text here would be both incomplete and would
corrupt legitimate content).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from testpilot.ai_provider.base import CitableEntityType
from testpilot.execution.artifact_models import Artifact
from testpilot.execution.models import TestResult, TestRun
from testpilot.issues.models import Issue
from testpilot.projects.models import Project
from testpilot.testcases.models import TestCase, TestStep

# Deliberately small and explicit so a large project can never balloon a
# single chat request into an enormous model call — tuned for "enough to be
# useful," not maximum grounding quality.
MAX_TEST_CASES = 15
MAX_TEST_STEPS_PER_CASE = 8
MAX_RECENT_RUNS = 5
MAX_RESULTS_PER_RUN = 10
MAX_ISSUES = 10
MAX_ARTIFACTS_PER_RESULT = 3
MAX_TEXT_FIELD_CHARS = 500


def _truncate(text: str | None, limit: int = MAX_TEXT_FIELD_CHARS) -> str | None:
    if text is None or len(text) <= limit:
        return text
    return text[:limit] + "…[truncated]"


async def build_project_context(
    session: AsyncSession, *, organization_id: uuid.UUID, project_id: uuid.UUID
) -> dict[str, Any] | None:
    """A bounded snapshot of one project's testing state, or `None` if the
    project doesn't exist/belong to `organization_id` (caller has already
    checked this via `_get_project_or_404`-style lookup, so this is a
    defense-in-depth `None` rather than a raised error)."""
    project_result = await session.execute(
        select(Project).where(Project.id == project_id, Project.organization_id == organization_id)
    )
    project = project_result.scalar_one_or_none()
    if project is None:
        return None

    context: dict[str, Any] = {
        "project": {"name": project.name, "url": project.url, "status": project.status.value}
    }
    context["test_cases"] = await _build_test_cases(session, organization_id=organization_id, project_id=project_id)
    context["recent_runs"] = await _build_recent_runs(session, organization_id=organization_id, project_id=project_id)
    context["issues"] = await _build_issues(session, organization_id=organization_id, project_id=project_id)
    return context


@dataclass(frozen=True)
class CitableEntity:
    """One entity from a request's own `grounding_data` that the assistant is
    allowed to cite (FR-102) — `title`/`url` are resolved server-side from
    data the server itself fetched, never from anything the model supplies."""

    entity_type: CitableEntityType
    entity_id: str
    title: str
    url: str


def extract_citable_entities(
    grounding_data: dict[str, Any] | None, *, project_id: uuid.UUID
) -> dict[str, CitableEntity]:
    """Indexes every citable entity (FR-102: test case, run, issue — not
    artifacts or individual test results, which the requirement doesn't
    name) actually present in `grounding_data`, keyed by
    `"{entity_type}:{entity_id}"`.

    Built by walking the SAME dict that was sent to the model, never a fresh
    query, so this index can never diverge from what the model actually saw:
    a citation validated against this index (assistant/service.py) is
    provably an entity the requesting user was already authorized to see in
    this exact request — never a hallucinated, foreign-Organization, or
    prompt-injected reference, regardless of what the model claims.
    """
    if not grounding_data:
        return {}

    index: dict[str, CitableEntity] = {}
    for test_case in grounding_data.get("test_cases", []):
        index[f"test_case:{test_case['id']}"] = CitableEntity(
            entity_type="test_case",
            entity_id=test_case["id"],
            title=test_case["title"],
            url=f"/projects/{project_id}/test-cases/{test_case['id']}",
        )
    for run in grounding_data.get("recent_runs", []):
        summary = run.get("summary", {})
        index[f"test_run:{run['id']}"] = CitableEntity(
            entity_type="test_run",
            entity_id=run["id"],
            title=f"Test run — {run['status']} ({summary.get('passed', 0)}/{summary.get('total', 0)} passed)",
            url=f"/projects/{project_id}/test-runs/{run['id']}",
        )
    for issue in grounding_data.get("issues", []):
        index[f"issue:{issue['id']}"] = CitableEntity(
            entity_type="issue",
            entity_id=issue["id"],
            title=issue["title"],
            url=f"/projects/{project_id}/issues/{issue['id']}",
        )
    return index


async def _build_test_cases(
    session: AsyncSession, *, organization_id: uuid.UUID, project_id: uuid.UUID
) -> list[dict[str, Any]]:
    # TestCasePriority is declared low->critical (testcases/models.py), so
    # Postgres's enum column ordering makes `.desc()` return critical-first
    # without a separate rank mapping — the same trick FR-052 relies on.
    result = await session.execute(
        select(TestCase)
        .where(TestCase.organization_id == organization_id, TestCase.project_id == project_id)
        .order_by(TestCase.priority.desc(), TestCase.created_at.desc())
        .limit(MAX_TEST_CASES)
    )
    test_cases = list(result.scalars().all())
    if not test_cases:
        return []

    steps_result = await session.execute(
        select(TestStep)
        .where(
            TestStep.organization_id == organization_id,
            TestStep.test_case_id.in_([tc.id for tc in test_cases]),
        )
        .order_by(TestStep.test_case_id, TestStep.order_index)
    )
    steps_by_case: dict[uuid.UUID, list[TestStep]] = {}
    for step in steps_result.scalars().all():
        steps_by_case.setdefault(step.test_case_id, []).append(step)

    return [
        {
            "id": str(tc.id),
            "title": tc.title,
            "description": _truncate(tc.description),
            "priority": tc.priority.value,
            "severity": tc.severity.value,
            "status": tc.status.value,
            "last_result": tc.last_result.value,
            "steps": [
                {
                    "action_type": step.action_type.value,
                    "target": step.target_descriptor,
                    "expected": step.expected_assertion,
                }
                for step in steps_by_case.get(tc.id, [])[:MAX_TEST_STEPS_PER_CASE]
            ],
        }
        for tc in test_cases
    ]


async def _build_recent_runs(
    session: AsyncSession, *, organization_id: uuid.UUID, project_id: uuid.UUID
) -> list[dict[str, Any]]:
    runs_result = await session.execute(
        select(TestRun)
        .where(TestRun.organization_id == organization_id, TestRun.project_id == project_id)
        .order_by(TestRun.created_at.desc())
        .limit(MAX_RECENT_RUNS)
    )
    runs = list(runs_result.scalars().all())

    payloads = []
    for run in runs:
        results_result = await session.execute(
            select(TestResult)
            .where(TestResult.organization_id == organization_id, TestResult.test_run_id == run.id)
            .order_by(TestResult.started_at.desc())
            .limit(MAX_RESULTS_PER_RUN)
        )
        results = list(results_result.scalars().all())

        result_payloads = []
        for r in results:
            artifacts_result = await session.execute(
                select(Artifact)
                .where(Artifact.organization_id == organization_id, Artifact.test_result_id == r.id)
                .limit(MAX_ARTIFACTS_PER_RESULT)
            )
            result_payloads.append(
                {
                    "test_case_id": str(r.test_case_id),
                    "status": r.status.value,
                    "error_message": _truncate(r.error_message),
                    "failure_step_index": r.failure_step_index,
                    "duration_ms": r.duration_ms,
                    "artifacts": [
                        {"type": a.type.value, "content_type": a.content_type}
                        for a in artifacts_result.scalars().all()
                    ],
                }
            )

        payloads.append(
            {
                "id": str(run.id),
                "status": run.status.value,
                "summary": {
                    "total": run.summary_total,
                    "passed": run.summary_passed,
                    "failed": run.summary_failed,
                    "skipped": run.summary_skipped,
                },
                "created_at": run.created_at.isoformat(),
                "results": result_payloads,
            }
        )
    return payloads


async def _build_issues(
    session: AsyncSession, *, organization_id: uuid.UUID, project_id: uuid.UUID
) -> list[dict[str, Any]]:
    result = await session.execute(
        select(Issue)
        .where(Issue.organization_id == organization_id, Issue.project_id == project_id)
        .order_by(Issue.created_at.desc())
        .limit(MAX_ISSUES)
    )
    return [
        {
            "id": str(issue.id),
            "title": issue.title,
            "description": _truncate(issue.description),
            "severity": issue.severity.value,
            "priority": issue.priority.value,
            "status": issue.status.value,
        }
        for issue in result.scalars().all()
    ]
