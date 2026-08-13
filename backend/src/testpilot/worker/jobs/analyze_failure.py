"""`AnalyzeFailureJob` handler (contracts/worker-jobs.md, T162).

Same asyncio.run-per-invocation bridge as the other worker job handlers —
see worker/jobs/generate_test_cases.py's docstring for why.
"""

import asyncio
import time
import uuid

from testpilot.ai_analysis import service as ai_analysis_service
from testpilot.ai_provider import get_provider
from testpilot.core.db import dispose_engine
from testpilot.core.logging import bind_context
from testpilot.core.metrics import record_job_outcome

_JOB_TYPE = "ai-analysis"


def handle(ai_analysis_id: str, organization_id: str, test_result_id: str, correlation_id: str) -> None:
    asyncio.run(
        _handle_async(
            uuid.UUID(ai_analysis_id), uuid.UUID(organization_id), uuid.UUID(test_result_id), correlation_id
        )
    )


async def _handle_async(
    ai_analysis_id: uuid.UUID, organization_id: uuid.UUID, test_result_id: uuid.UUID, correlation_id: str
) -> None:
    bind_context(correlation_id=correlation_id, organization_id=str(organization_id))
    started_at = time.monotonic()
    status = "success"
    try:
        await ai_analysis_service.run_analysis(
            ai_analysis_id=ai_analysis_id,
            organization_id=organization_id,
            test_result_id=test_result_id,
            provider=get_provider(),
            storage=None,
        )
    except Exception:
        status = "failure"
        raise
    finally:
        await dispose_engine()
        record_job_outcome(job_type=_JOB_TYPE, status=status, duration_seconds=time.monotonic() - started_at)
