"""Site-analysis step (plan.md AI Test-Case Generation Architecture): a
lightweight same-worker crawl of a project's publicly reachable pages,
bounded page count and depth, reusing `BrowserAutomationEngine.load_page`
(not duplicating it — "both need 'load a page and read its DOM'").
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from testpilot.ai_provider.base import PageSnapshot, SiteAnalysisContext
from testpilot.execution.engine import BrowserAutomationEngine

DEFAULT_MAX_PAGES = 5


class NoPublicContentError(Exception):
    """FR-045: raised when zero pages could be successfully loaded — the
    target may require authentication (redirects to a login page) or
    otherwise expose no reachable public content."""


def _same_origin(url: str, base_url: str) -> bool:
    a, b = urlparse(url), urlparse(base_url)
    return (a.scheme, a.netloc) == (b.scheme, b.netloc)


async def analyze_site(
    *,
    engine: BrowserAutomationEngine,
    project_name: str,
    base_url: str,
    preferences: dict[str, Any] | None = None,
    max_pages: int = DEFAULT_MAX_PAGES,
) -> SiteAnalysisContext:
    visited: set[str] = set()
    queue: list[str] = [base_url]
    pages: list[PageSnapshot] = []

    while queue and len(pages) < max_pages:
        url = queue.pop(0)
        if url in visited:
            continue
        visited.add(url)
        try:
            loaded = await engine.load_page(url)
        except Exception:  # noqa: BLE001 — an unreachable page is skipped, not fatal to the whole crawl
            continue
        pages.append(loaded.to_page_snapshot())
        for link in loaded.links:
            if link not in visited and _same_origin(link, base_url):
                queue.append(link)

    if not pages:
        raise NoPublicContentError(f"No testable public content was found at {base_url}")

    return SiteAnalysisContext(
        project_name=project_name, project_url=base_url, pages=pages, preferences=preferences or {}
    )
