"""`GenerateTestCasesJob` handler (contracts/worker-jobs.md, T118).

RQ calls job functions synchronously in a worker process; `handle` bridges
into the async orchestration via `asyncio.run(...)`, the same pattern
already established for CLI commands (cli/billing.py's `_run` helper) —
each invocation gets its own event loop and disposes the cached DB engine
afterward so the next invocation (in the same long-lived worker process)
doesn't reuse connections bound to a closed loop.
"""

import asyncio
import time
import uuid

from testpilot.ai_generation import service as ai_generation_service
from testpilot.ai_provider import get_provider
from testpilot.core.db import dispose_engine
from testpilot.core.logging import bind_context
from testpilot.core.metrics import record_job_outcome
from testpilot.execution.playwright_engine import PlaywrightEngine

_JOB_TYPE = "ai-generation"


def handle(generation_run_id: str, organization_id: str, correlation_id: str) -> None:
    asyncio.run(_handle_async(uuid.UUID(generation_run_id), uuid.UUID(organization_id), correlation_id))


async def _handle_async(generation_run_id: uuid.UUID, organization_id: uuid.UUID, correlation_id: str) -> None:
    bind_context(correlation_id=correlation_id, organization_id=str(organization_id))
    started_at = time.monotonic()
    status = "success"
    engine = PlaywrightEngine()
    try:
        await ai_generation_service.run_generation(
            generation_run_id=generation_run_id,
            organization_id=organization_id,
            provider=get_provider(),
            engine=engine,
        )
    except Exception:
        status = "failure"
        raise
    finally:
        await engine.close()
        await dispose_engine()
        record_job_outcome(job_type=_JOB_TYPE, status=status, duration_seconds=time.monotonic() - started_at)
