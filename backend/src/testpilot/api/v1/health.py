from fastapi import APIRouter, Response, status
from prometheus_client import CONTENT_TYPE_LATEST, REGISTRY, generate_latest
from sqlalchemy import text

from testpilot.core.db import get_engine
from testpilot.core.metrics import queue_depth_collector
from testpilot.core.redis import get_redis
from testpilot.worker.queues import ai_analysis_queue, ai_generation_queue, test_execution_queue

router = APIRouter(tags=["health"])

_QUEUE_GETTERS = {
    "ai-generation": ai_generation_queue,
    "test-execution": test_execution_queue,
    "ai-analysis": ai_analysis_queue,
}
# Registered once at import time, not per-request — `prometheus_client`
# raises if the same collector name is registered twice on one registry,
# and the default global `REGISTRY` persists for the process's lifetime.
REGISTRY.register(queue_depth_collector(lambda name: _QUEUE_GETTERS[name]()))


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    """Liveness: the process is up. No dependency checks — used by container
    orchestration liveness probes, which should restart the process only if
    the process itself is wedged, not if a downstream dependency is briefly
    unavailable (that's what readyz is for)."""
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(response: Response) -> dict[str, object]:
    """Readiness: the process can actually serve traffic (DB and Redis reachable)."""
    checks: dict[str, str] = {}

    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001 - readiness probe must not raise
        checks["database"] = f"unavailable: {exc}"

    try:
        await get_redis().ping()
        checks["redis"] = "ok"
    except Exception as exc:  # noqa: BLE001 - readiness probe must not raise
        checks["redis"] = f"unavailable: {exc}"

    all_ok = all(v == "ok" for v in checks.values())
    if not all_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ok" if all_ok else "unavailable", "checks": checks}


@router.get("/metrics")
async def metrics() -> Response:
    """NFR-011: automatic HTTP request metrics come from
    `prometheus-fastapi-instrumentator` (wired in api/main.py, recording
    into this same default global registry); `testpilot_queue_depth` comes
    from the collector registered above. No authentication — Prometheus
    scrapers don't send a Bearer token, and none of these metrics carry
    per-tenant or per-user data."""
    return Response(content=generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)
