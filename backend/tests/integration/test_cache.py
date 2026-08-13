"""T220: generic Redis get-or-set caching helper (NFR-008). Uses the real
test Redis instance (already required by every other test in this suite,
`_clean_queues` in conftest.py flushes it before each test) rather than a
fake, since this module's whole job is to be a thin, correct wrapper
around real Redis GET/SET/DELETE semantics.
"""

import uuid

import pytest
from sqlmodel import SQLModel

from testpilot.core import cache

pytestmark = pytest.mark.anyio


class _Widget(SQLModel):
    id: uuid.UUID
    name: str
    count: int = 0


async def test_get_or_set_model_calls_the_loader_on_a_cache_miss():
    calls = []

    async def _loader() -> _Widget:
        calls.append(1)
        return _Widget(id=uuid.uuid4(), name="first", count=1)

    result = await cache.get_or_set_model(namespace="widget", key="miss-key", model_cls=_Widget, loader=_loader)

    assert result.name == "first"
    assert len(calls) == 1


async def test_get_or_set_model_does_not_call_the_loader_again_on_a_cache_hit():
    calls = []
    widget_id = uuid.uuid4()

    async def _loader() -> _Widget:
        calls.append(1)
        return _Widget(id=widget_id, name="cached", count=len(calls))

    first = await cache.get_or_set_model(namespace="widget", key="hit-key", model_cls=_Widget, loader=_loader)
    second = await cache.get_or_set_model(namespace="widget", key="hit-key", model_cls=_Widget, loader=_loader)

    assert len(calls) == 1
    assert first == second
    assert second.count == 1  # proves the loader's second invocation never happened


async def test_invalidate_forces_the_next_call_to_reload():
    calls = []

    async def _loader() -> _Widget:
        calls.append(1)
        return _Widget(id=uuid.uuid4(), name=f"version-{len(calls)}", count=len(calls))

    await cache.get_or_set_model(namespace="widget", key="invalidate-key", model_cls=_Widget, loader=_loader)
    await cache.invalidate(namespace="widget", key="invalidate-key")
    result = await cache.get_or_set_model(namespace="widget", key="invalidate-key", model_cls=_Widget, loader=_loader)

    assert len(calls) == 2
    assert result.name == "version-2"


async def test_get_or_set_model_does_not_cache_a_none_result():
    calls = []

    async def _loader() -> _Widget | None:
        calls.append(1)
        return None

    first = await cache.get_or_set_model(namespace="widget", key="none-key", model_cls=_Widget, loader=_loader)
    second = await cache.get_or_set_model(namespace="widget", key="none-key", model_cls=_Widget, loader=_loader)

    assert first is None
    assert second is None
    assert len(calls) == 2  # a None loader result is never cached, so both calls hit the loader


async def test_different_namespaces_do_not_collide_on_the_same_key():
    async def _loader_a() -> _Widget:
        return _Widget(id=uuid.uuid4(), name="namespace-a", count=1)

    async def _loader_b() -> _Widget:
        return _Widget(id=uuid.uuid4(), name="namespace-b", count=2)

    result_a = await cache.get_or_set_model(namespace="widget-a", key="shared-key", model_cls=_Widget, loader=_loader_a)
    result_b = await cache.get_or_set_model(namespace="widget-b", key="shared-key", model_cls=_Widget, loader=_loader_b)

    assert result_a.name == "namespace-a"
    assert result_b.name == "namespace-b"
