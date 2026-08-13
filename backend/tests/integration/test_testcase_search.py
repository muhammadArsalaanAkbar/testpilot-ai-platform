"""Integration test: full-text search plus tag/priority/severity/status
filters, combined, against a realistic seeded set of test cases (T099,
FR-050, FR-051). The contract tests (test_testcases.py) check each filter
works in isolation against the real API shape; this proves the query
builder combines predicates correctly (AND semantics) and that full-text
search matches on both title and description.
"""

import pytest


async def _signup_and_get_token(client, email="tc-search@example.com"):
    r = await client.post(
        "/auth/signup", json={"email": email, "password": "correct horse battery staple", "name": "Search Test"}
    )
    return r.json()["access_token"]


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _seed_cases(client, project_id, token):
    headers = _auth_headers(token)
    cases = [
        {
            "title": "Checkout with valid credit card",
            "description": "Verify a shopper can complete checkout using a valid card.",
            "priority": "critical",
            "severity": "blocker",
            "tags": ["checkout", "payments"],
        },
        {
            "title": "Checkout with expired credit card",
            "description": "Verify checkout rejects an expired card with a clear error.",
            "priority": "high",
            "severity": "major",
            "tags": ["checkout", "payments", "negative"],
        },
        {
            "title": "Search returns relevant results",
            "description": "Verify the product search bar returns matching items.",
            "priority": "medium",
            "severity": "minor",
            "tags": ["search"],
        },
        {
            "title": "Profile picture upload",
            "description": "Verify a user can upload and crop a profile picture.",
            "priority": "low",
            "severity": "minor",
            "tags": ["profile"],
        },
    ]
    ids = {}
    for case in cases:
        r = await client.post(f"/projects/{project_id}/test-cases", json=case, headers=headers)
        ids[case["title"]] = r.json()["id"]
    return ids


@pytest.mark.anyio
async def test_search_and_filters_combine_correctly(client):
    token = await _signup_and_get_token(client)
    project = await client.post(
        "/projects", json={"name": "Search Project", "url": "https://example.com"}, headers=_auth_headers(token)
    )
    project_id = project.json()["id"]
    ids = await _seed_cases(client, project_id, token)
    headers = _auth_headers(token)

    # Full-text search matches title and description (FR-050).
    checkout_search = await client.get(f"/projects/{project_id}/test-cases?q=checkout", headers=headers)
    assert {c["id"] for c in checkout_search.json()["items"]} == {
        ids["Checkout with valid credit card"],
        ids["Checkout with expired credit card"],
    }

    description_search = await client.get(f"/projects/{project_id}/test-cases?q=crop", headers=headers)
    assert {c["id"] for c in description_search.json()["items"]} == {ids["Profile picture upload"]}

    # Combined tag + priority filter (AND semantics).
    combined = await client.get(
        f"/projects/{project_id}/test-cases?tag=payments&priority=critical", headers=headers
    )
    assert {c["id"] for c in combined.json()["items"]} == {ids["Checkout with valid credit card"]}

    # Combined search + severity filter.
    search_and_severity = await client.get(
        f"/projects/{project_id}/test-cases?q=checkout&severity=major", headers=headers
    )
    assert {c["id"] for c in search_and_severity.json()["items"]} == {
        ids["Checkout with expired credit card"]
    }

    # A search + filter combination matching nothing returns an empty list, not an error.
    empty = await client.get(f"/projects/{project_id}/test-cases?q=checkout&tag=profile", headers=headers)
    assert empty.status_code == 200
    assert empty.json()["items"] == []

    # Status filter after approving one case.
    await client.post(
        f"/projects/{project_id}/test-cases/{ids['Search returns relevant results']}/approve", headers=headers
    )
    approved = await client.get(f"/projects/{project_id}/test-cases?status_filter=approved", headers=headers)
    assert {c["id"] for c in approved.json()["items"]} == {ids["Search returns relevant results"]}

    draft = await client.get(f"/projects/{project_id}/test-cases?status_filter=draft", headers=headers)
    assert {c["id"] for c in draft.json()["items"]} == {
        ids["Checkout with valid credit card"],
        ids["Checkout with expired credit card"],
        ids["Profile picture upload"],
    }

    # No filters at all returns everything for the project.
    everything = await client.get(f"/projects/{project_id}/test-cases", headers=headers)
    assert len(everything.json()["items"]) == 4
