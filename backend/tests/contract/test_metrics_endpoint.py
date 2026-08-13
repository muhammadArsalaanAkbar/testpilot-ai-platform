"""T218: `GET /metrics` (contract: no auth — Prometheus scrapers don't send
a Bearer token, and metrics themselves carry no per-tenant/user data) is
Prometheus-text-format and includes both the automatic HTTP request
metrics (`prometheus-fastapi-instrumentator`) and the custom
`testpilot_queue_depth` gauge (core/metrics.py, backed by the real Redis
queues this environment already runs against — no fake queue needed, the
test DB/Redis setup is real per every other integration test in this
suite).
"""

import pytest

pytestmark = pytest.mark.anyio


async def test_metrics_endpoint_returns_prometheus_text_format(client):
    response = await client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")


async def test_metrics_endpoint_requires_no_authentication(client):
    # No Authorization header at all -- must not 401, unlike every real
    # business endpoint.
    response = await client.get("/metrics")
    assert response.status_code == 200


async def test_metrics_endpoint_reports_queue_depth_for_all_three_queues(client):
    response = await client.get("/metrics")
    body = response.text
    assert 'testpilot_queue_depth{queue_name="ai-generation"}' in body
    assert 'testpilot_queue_depth{queue_name="test-execution"}' in body
    assert 'testpilot_queue_depth{queue_name="ai-analysis"}' in body
