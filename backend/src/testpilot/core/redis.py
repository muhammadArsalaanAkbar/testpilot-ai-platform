import contextlib

from redis.asyncio import Redis

from testpilot.core.config import get_settings

_redis: Redis | None = None


def get_redis() -> Redis:
    """Shared async Redis client, used for the job queue, rate limiting, and cache."""
    global _redis
    if _redis is None:
        _redis = Redis.from_url(get_settings().redis_url, decode_responses=True)
    return _redis


async def dispose_redis() -> None:
    """Mirrors `core/db.py::dispose_engine` — this module's cached client is
    a process-lifetime singleton by design, but its underlying connections
    are bound to whichever asyncio event loop was running when they were
    opened. pytest-asyncio gives each test function its own event loop, so
    without resetting this between tests, a second test to use `get_redis()`
    reuses connections bound to a now-closed loop (`RuntimeError: Event
    loop is closed`) — the same failure mode `_fresh_engine_per_test`
    (tests/conftest.py) already exists to prevent for the DB engine.

    The `RuntimeError` this guards against can also surface *from*
    `.aclose()` itself, not just from later reuse: if the cached client's
    loop was already torn down by the time this runs (e.g. a CLI test
    helper's own separate `asyncio.run()` call, sequenced before this one,
    already closed it), there is nothing left to gracefully close — the
    goal here is only to drop the stale reference so the next `get_redis()`
    call builds a fresh client bound to the *current* loop, so that specific
    failure is expected and safe to ignore rather than let propagate.
    """
    global _redis
    if _redis is not None:
        with contextlib.suppress(RuntimeError):
            await _redis.aclose()
    _redis = None
