"""RQ queue definitions (research.md #5): three logical queues so a burst
of one job type cannot starve another, each consumed by dedicated worker
processes.

RQ itself is sync (its worker model forks/threads, not asyncio), so this
module uses a plain `redis.Redis` connection — distinct from `core/redis.py`'s
`redis.asyncio.Redis` used everywhere else in the API process.
"""

import redis
from rq import Queue

from testpilot.core.config import get_settings

AI_GENERATION_QUEUE = "ai-generation"
TEST_EXECUTION_QUEUE = "test-execution"
AI_ANALYSIS_QUEUE = "ai-analysis"

_sync_redis: redis.Redis | None = None


def get_sync_redis() -> redis.Redis:
    global _sync_redis
    if _sync_redis is None:
        _sync_redis = redis.Redis.from_url(get_settings().redis_url)
    return _sync_redis


def ai_generation_queue() -> Queue:
    return Queue(AI_GENERATION_QUEUE, connection=get_sync_redis())


def test_execution_queue() -> Queue:
    return Queue(TEST_EXECUTION_QUEUE, connection=get_sync_redis())


def ai_analysis_queue() -> Queue:
    return Queue(AI_ANALYSIS_QUEUE, connection=get_sync_redis())
