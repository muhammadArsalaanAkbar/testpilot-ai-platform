"""Contract tests for SEC-009/FR-132 rate limiting on AI generation/analysis
and test-execution-trigger endpoints (T199). The global limiter is disabled
in the test environment by default (api/deps.py's own module docstring) so
unrelated tests never incidentally trip it — each test here flips
`limiter.enabled` on for its own duration only, and always resets it in a
`finally` block so it never leaks into any other test.
"""

import pytest

from testpilot.api.deps import limiter


async def _signup_and_get_token(client, email="rate-limit-contract@example.com"):
    r = await client.post(
        "/auth/signup", json={"email": email, "password": "correct horse battery staple", "name": "Rate Limit Test"}
    )
    return r.json()["access_token"]


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _create_project(client, token, name="Rate Limit Project"):
    r = await client.post("/projects", json={"name": name, "url": "https://example.com"}, headers=_auth_headers(token))
    return r.json()["id"]


async def _create_approved_test_case(client, token, project_id, title="Case"):
    r = await client.post(
        f"/projects/{project_id}/test-cases",
        json={
            "title": title,
            "description": "d",
            "priority": "medium",
            "severity": "minor",
            "steps": [{"action_type": "navigate", "target_descriptor": "/"}],
        },
        headers=_auth_headers(token),
    )
    case_id = r.json()["id"]
    await client.post(f"/projects/{project_id}/test-cases/{case_id}/approve", headers=_auth_headers(token))
    return case_id


@pytest.mark.anyio
async def test_ai_generation_endpoint_is_rate_limited(client):
    token = await _signup_and_get_token(client, email="rl-generation@example.com")
    project_id = await _create_project(client, token)

    limiter.enabled = True
    try:
        statuses = [
            (await client.post(f"/projects/{project_id}/test-cases/generate", headers=_auth_headers(token))).status_code
            for _ in range(12)
        ]
    finally:
        limiter.enabled = False

    assert 429 in statuses


@pytest.mark.anyio
async def test_ai_analysis_endpoint_is_rate_limited(client):
    token = await _signup_and_get_token(client, email="rl-analysis@example.com")
    project_id = await _create_project(client, token)
    case_id = await _create_approved_test_case(client, token, project_id)
    run_response = await client.post(
        f"/projects/{project_id}/test-runs", json={"test_case_ids": [case_id]}, headers=_auth_headers(token)
    )
    run_id = run_response.json()["id"]
    # No worker consumes the test queue during pytest (conftest.py's
    # _clean_queues docstring) -- the run stays "queued" with no results,
    # so there is no failed test_result_id to call /analyze against. The
    # rate limiter fires on the request itself before any business-logic
    # validation of the (nonexistent) result runs, so a 404 for a made-up
    # result id is an equally valid target for exhausting the limit.
    fake_result_id = "00000000-0000-0000-0000-000000000000"

    limiter.enabled = True
    try:
        statuses = [
            (
                await client.post(
                    f"/projects/{project_id}/test-runs/{run_id}/results/{fake_result_id}/analyze",
                    headers=_auth_headers(token),
                )
            ).status_code
            for _ in range(12)
        ]
    finally:
        limiter.enabled = False

    assert 429 in statuses


@pytest.mark.anyio
async def test_test_execution_trigger_endpoint_is_rate_limited(client):
    token = await _signup_and_get_token(client, email="rl-execution@example.com")
    project_id = await _create_project(client, token)
    case_id = await _create_approved_test_case(client, token, project_id)

    limiter.enabled = True
    try:
        statuses = [
            (
                await client.post(
                    f"/projects/{project_id}/test-runs", json={"test_case_ids": [case_id]}, headers=_auth_headers(token)
                )
            ).status_code
            for _ in range(12)
        ]
    finally:
        limiter.enabled = False

    assert 429 in statuses


@pytest.mark.anyio
async def test_unrelated_endpoint_is_not_rate_limited_by_the_same_bucket(client):
    """A sanity check that the limiter is per-route (slowapi's default),
    not a global request counter that would make every other endpoint
    flaky once one route gets busy."""
    token = await _signup_and_get_token(client, email="rl-unrelated@example.com")

    limiter.enabled = True
    try:
        statuses = [
            (await client.get("/projects", headers=_auth_headers(token))).status_code for _ in range(12)
        ]
    finally:
        limiter.enabled = False

    assert all(status == 200 for status in statuses)
