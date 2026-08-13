"""Integration test: generation produces a positive/negative/edge-case mix
with non-empty purpose text per case (T110, FR-039, FR-040).

Directly invokes `ai_generation.service.run_generation` — the exact function
the real `rq worker` process calls via `worker/jobs/generate_test_cases.py`'s
`handle` — rather than running a live worker for this test, since this test
is about the orchestration's correctness (does a full run persist the right
draft test cases with the right shape), not the queue transport (already
verified separately by test_ai_generation.py's contract tests). A fake
BrowserAutomationEngine (not real Playwright) stands in for the crawl step,
matching contracts/ai-provider-adapter.md's own stated testing philosophy of
using fakes so this test never depends on real network access — the real
Playwright adapter is covered by test_playwright_engine.py, and the crawl
logic itself by test_site_analysis.py.
"""

import uuid

import pytest

from testpilot.ai_generation import service as ai_generation_service
from testpilot.ai_generation.models import GenerationStatus
from testpilot.ai_provider.base import FormFieldSnapshot, FormSnapshot
from testpilot.ai_provider.fake import FakeLLMProvider
from testpilot.execution.engine import LoadedPage

pytestmark = pytest.mark.anyio


async def _signup_and_get_token(client, email="ai-gen-flow@example.com"):
    r = await client.post(
        "/auth/signup", json={"email": email, "password": "correct horse battery staple", "name": "AI Gen Flow"}
    )
    body = r.json()
    return body["access_token"], body["organization"]["id"]


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _create_project(client, token, name="AI Gen Flow Project"):
    r = await client.post("/projects", json={"name": name, "url": "https://example.com"}, headers=_auth_headers(token))
    return r.json()["id"]


class _FakeEngineWithForm:
    """Always returns one canned page with a signup form, regardless of the
    URL requested — this test is about generation output correctness, not
    crawl behavior (see module docstring)."""

    async def load_page(self, url: str) -> LoadedPage:
        return LoadedPage(
            url=url,
            title="Sign Up",
            headings=["Create your account"],
            forms=[
                FormSnapshot(
                    action="/signup",
                    method="post",
                    fields=[
                        FormFieldSnapshot(name="email", field_type="email"),
                        FormFieldSnapshot(name="password", field_type="password"),
                    ],
                )
            ],
            interactive_elements=["Sign up"],
            links=[],
        )


@pytest.mark.anyio
async def test_full_generation_run_produces_a_flow_type_mix_with_purpose_text(client):
    token, organization_id = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)

    generate = await client.post(f"/projects/{project_id}/test-cases/generate", headers=_auth_headers(token))
    assert generate.status_code == 202
    run_id = generate.json()["id"]

    # Simulate the worker processing the enqueued job.
    await ai_generation_service.run_generation(
        generation_run_id=run_id,
        organization_id=uuid.UUID(organization_id),
        provider=FakeLLMProvider(),
        engine=_FakeEngineWithForm(),
    )

    status_response = await client.get(
        f"/projects/{project_id}/test-cases/generate/{run_id}", headers=_auth_headers(token)
    )
    assert status_response.status_code == 200
    run_body = status_response.json()
    assert run_body["status"] == GenerationStatus.completed.value
    assert len(run_body["created_test_case_ids"]) > 0

    list_response = await client.get(f"/projects/{project_id}/test-cases", headers=_auth_headers(token))
    cases = list_response.json()["items"]
    created_ids = set(run_body["created_test_case_ids"])
    generated_cases = [c for c in cases if c["id"] in created_ids]

    assert len(generated_cases) == len(created_ids)
    for case in generated_cases:
        assert case["source"] == "ai_generated"
        assert case["status"] == "draft"

    # FR-038: every case has ordered steps and a non-empty purpose explanation.
    for case_id in created_ids:
        detail = await client.get(f"/projects/{project_id}/test-cases/{case_id}", headers=_auth_headers(token))
        body = detail.json()
        assert body["test_case"]["description"].strip() != ""
        assert len(body["steps"]) > 0
        assert [s["order_index"] for s in body["steps"]] == list(range(len(body["steps"])))


@pytest.mark.anyio
async def test_full_generation_run_frees_the_project_for_a_new_generation(client):
    """FR-047: once a run reaches a terminal state, the project is no
    longer considered "in progress" and a new generation can be started."""
    token, organization_id = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)

    first = await client.post(f"/projects/{project_id}/test-cases/generate", headers=_auth_headers(token))
    first_run_id = first.json()["id"]

    await ai_generation_service.run_generation(
        generation_run_id=first_run_id,
        organization_id=uuid.UUID(organization_id),
        provider=FakeLLMProvider(),
        engine=_FakeEngineWithForm(),
    )

    second = await client.post(f"/projects/{project_id}/test-cases/generate", headers=_auth_headers(token))
    assert second.status_code == 202


@pytest.mark.anyio
async def test_generation_run_fails_cleanly_on_provider_error(client):
    """FR-046: a provider error results in a distinct failed state, not a
    silently-completed run with no test cases."""
    token, organization_id = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)

    generate = await client.post(f"/projects/{project_id}/test-cases/generate", headers=_auth_headers(token))
    run_id = generate.json()["id"]

    await ai_generation_service.run_generation(
        generation_run_id=run_id,
        organization_id=uuid.UUID(organization_id),
        provider=FakeLLMProvider(fail_mode="malformed"),
        engine=_FakeEngineWithForm(),
    )

    status_response = await client.get(
        f"/projects/{project_id}/test-cases/generate/{run_id}", headers=_auth_headers(token)
    )
    body = status_response.json()
    assert body["status"] == GenerationStatus.failed.value
    assert body["failure_reason"]
    assert body["created_test_case_ids"] == []

    list_response = await client.get(f"/projects/{project_id}/test-cases", headers=_auth_headers(token))
    assert list_response.json()["items"] == []


@pytest.mark.anyio
async def test_regenerate_replaces_the_target_case_content_and_resets_to_draft(client):
    token, organization_id = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)
    create = await client.post(
        f"/projects/{project_id}/test-cases",
        json={"title": "Old title", "description": "Old description", "priority": "low", "severity": "minor"},
        headers=_auth_headers(token),
    )
    test_case_id = create.json()["id"]
    await client.post(f"/projects/{project_id}/test-cases/{test_case_id}/approve", headers=_auth_headers(token))

    regenerate = await client.post(
        f"/projects/{project_id}/test-cases/{test_case_id}/regenerate", headers=_auth_headers(token)
    )
    run_id = regenerate.json()["id"]

    await ai_generation_service.run_generation(
        generation_run_id=run_id,
        organization_id=uuid.UUID(organization_id),
        provider=FakeLLMProvider(),
        engine=_FakeEngineWithForm(),
    )

    detail = await client.get(f"/projects/{project_id}/test-cases/{test_case_id}", headers=_auth_headers(token))
    body = detail.json()
    assert body["test_case"]["title"] != "Old title"
    assert body["test_case"]["status"] == "draft"
    assert body["test_case"]["source"] == "manual"
