"""AI provider selection (research.md #7): `AI_PROVIDER` env var selects the
concrete adapter; callers depend only on the `LLMProvider` Protocol, never a
specific adapter class (NFR-018/INT-002)."""

from functools import lru_cache

from testpilot.ai_provider.base import LLMProvider
from testpilot.core.config import get_settings


@lru_cache
def get_provider() -> LLMProvider:
    settings = get_settings()
    if settings.ai_provider == "fake":
        from testpilot.ai_provider.fake import FakeLLMProvider

        return FakeLLMProvider()

    from testpilot.ai_provider.cloud import CloudLLMProvider

    return CloudLLMProvider()
