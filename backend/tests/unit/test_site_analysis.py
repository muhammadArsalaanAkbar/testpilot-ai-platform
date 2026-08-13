"""Unit tests for the ai_generation site-analysis crawl step (T115).

Uses an in-memory fake BrowserAutomationEngine (not a real browser) so
crawl-logic (bounded depth/count, same-origin filtering, skip-on-error,
FR-045 no-public-content) is tested fast and deterministically — the real
Playwright adapter itself is covered by tests/integration/test_playwright_engine.py.
"""

import pytest

from testpilot.ai_generation.analysis import NoPublicContentError, analyze_site
from testpilot.execution.engine import LoadedPage

pytestmark = pytest.mark.anyio


class _FakeEngine:
    def __init__(self, pages: dict[str, LoadedPage], fail_urls: set[str] | None = None):
        self.pages = pages
        self.fail_urls = fail_urls or set()
        self.loaded_urls: list[str] = []

    async def load_page(self, url: str) -> LoadedPage:
        self.loaded_urls.append(url)
        if url in self.fail_urls:
            raise RuntimeError("simulated unreachable page")
        return self.pages[url]


def _page(url: str, links: list[str] | None = None) -> LoadedPage:
    return LoadedPage(url=url, title=url, headings=[], forms=[], interactive_elements=[], links=links or [])


async def test_analyze_site_follows_same_origin_links():
    pages = {
        "https://example.com": _page("https://example.com", links=["https://example.com/about"]),
        "https://example.com/about": _page("https://example.com/about"),
    }
    engine = _FakeEngine(pages)

    context = await analyze_site(engine=engine, project_name="Example", base_url="https://example.com")

    assert {p.url for p in context.pages} == set(pages.keys())


async def test_analyze_site_does_not_follow_cross_origin_links():
    pages = {
        "https://example.com": _page("https://example.com", links=["https://other.com/page"]),
    }
    engine = _FakeEngine(pages)

    context = await analyze_site(engine=engine, project_name="Example", base_url="https://example.com")

    assert {p.url for p in context.pages} == {"https://example.com"}
    assert "https://other.com/page" not in engine.loaded_urls


async def test_analyze_site_is_bounded_by_max_pages():
    pages = {f"https://example.com/{i}": _page(f"https://example.com/{i}", links=[f"https://example.com/{i + 1}"]) for i in range(10)}
    pages["https://example.com/0"] = _page("https://example.com/0", links=["https://example.com/1"])
    engine = _FakeEngine(pages)

    context = await analyze_site(
        engine=engine, project_name="Example", base_url="https://example.com/0", max_pages=3
    )

    assert len(context.pages) <= 3


async def test_analyze_site_does_not_revisit_pages():
    pages = {
        "https://example.com": _page(
            "https://example.com", links=["https://example.com/about", "https://example.com/about"]
        ),
        "https://example.com/about": _page("https://example.com/about", links=["https://example.com"]),
    }
    engine = _FakeEngine(pages)

    context = await analyze_site(engine=engine, project_name="Example", base_url="https://example.com")

    urls = [p.url for p in context.pages]
    assert len(urls) == len(set(urls))


async def test_analyze_site_skips_unreachable_pages_without_failing():
    pages = {
        "https://example.com": _page(
            "https://example.com", links=["https://example.com/broken", "https://example.com/about"]
        ),
        "https://example.com/about": _page("https://example.com/about"),
    }
    engine = _FakeEngine(pages, fail_urls={"https://example.com/broken"})

    context = await analyze_site(engine=engine, project_name="Example", base_url="https://example.com")

    assert {p.url for p in context.pages} == {"https://example.com", "https://example.com/about"}


async def test_analyze_site_raises_when_no_public_content_found():
    """FR-045: if the target redirects to a login page with no public
    content (simulated here as the base URL itself being unreachable),
    generation MUST report that no testable public content was found."""
    engine = _FakeEngine({}, fail_urls={"https://example.com"})

    with pytest.raises(NoPublicContentError):
        await analyze_site(engine=engine, project_name="Example", base_url="https://example.com")


async def test_analyze_site_includes_project_name_and_preferences():
    pages = {"https://example.com": _page("https://example.com")}
    engine = _FakeEngine(pages)

    context = await analyze_site(
        engine=engine,
        project_name="Example App",
        base_url="https://example.com",
        preferences={"focus": "checkout"},
    )

    assert context.project_name == "Example App"
    assert context.project_url == "https://example.com"
    assert context.preferences == {"focus": "checkout"}
