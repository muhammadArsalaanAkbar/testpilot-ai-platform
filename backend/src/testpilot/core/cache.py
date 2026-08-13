"""Generic Redis get-or-set caching helper (NFR-008): "caching of
frequently read, rarely changed data (e.g., project metadata, plan
limits) to reduce database load as tenant count grows."

Callers own the cache key's shape (namespace + key), the TTL, and —
critically — invalidation: this module has no write-path awareness of its
own, so every caller that uses it MUST call `invalidate(...)` from
whichever write path can change the cached value (see
`billing/service.py::set_plan_for_organization` and
`projects/service.py`'s update/archive/unarchive/delete paths for the two
call sites this module was built for).

A loader returning `None` (not found) is never cached — an MVP-scale
cache-stampede risk on repeated not-found lookups is an acceptable
trade-off against the alternative failure mode (a stale negative cache
masking a real row that exists as of a moment after the miss was cached).
"""

import json
from collections.abc import Awaitable, Callable

from sqlmodel import SQLModel

from testpilot.core.redis import get_redis

_DEFAULT_TTL_SECONDS = 60


def _redis_key(namespace: str, key: str) -> str:
    return f"cache:{namespace}:{key}"


async def get_or_set_model[T: SQLModel](
    *,
    namespace: str,
    key: str,
    model_cls: type[T],
    loader: Callable[[], Awaitable[T | None]],
    ttl_seconds: int = _DEFAULT_TTL_SECONDS,
) -> T | None:
    redis = get_redis()
    redis_key = _redis_key(namespace, key)

    cached = await redis.get(redis_key)
    if cached is not None:
        return model_cls.model_validate(json.loads(cached))

    value = await loader()
    if value is not None:
        await redis.set(redis_key, value.model_dump_json(), ex=ttl_seconds)
    return value


async def invalidate(*, namespace: str, key: str) -> None:
    await get_redis().delete(_redis_key(namespace, key))
