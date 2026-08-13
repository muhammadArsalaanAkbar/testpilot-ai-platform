"""`ExecuteTestRunJob` handler (contracts/worker-jobs.md, T141).

Same asyncio.run-per-invocation bridge as worker/jobs/generate_test_cases.py
— see that module's docstring for why. Uses the real `PlaywrightEngine`
(Phase 10, reused unmodified) — no mocked/fake engine in the production job
path, only in tests.
"""

import asyncio
import time
import uuid

from testpilot.core.db import dispose_engine
from testpilot.core.logging import bind_context
from testpilot.core.metrics import record_job_outcome
from testpilot.execution import runner
from testpilot.execution.playwright_engine import PlaywrightEngine

_JOB_TYPE = "test-execution"


def handle(test_run_id: str, organization_id: str, correlation_id: str) -> None:
    asyncio.run(_handle_async(uuid.UUID(test_run_id), uuid.UUID(organization_id), correlation_id))


async def _handle_async(test_run_id: uuid.UUID, organization_id: uuid.UUID, correlation_id: str) -> None:
    # contracts/worker-jobs.md's shared envelope (T217): every log
    # statement this job's own code and the service layer it calls make
    # from here on carries the same correlation_id the API request that
    # enqueued it logged under.
    bind_context(correlation_id=correlation_id, organization_id=str(organization_id))
    started_at = time.monotonic()
    status = "success"
    engine = PlaywrightEngine()
    try:
        await runner.run_test_run(test_run_id=test_run_id, organization_id=organization_id, engine=engine)
    except Exception:
        status = "failure"
        raise
    finally:
        await engine.close()
        await dispose_engine()
        record_job_outcome(job_type=_JOB_TYPE, status=status, duration_seconds=time.monotonic() - started_at)
