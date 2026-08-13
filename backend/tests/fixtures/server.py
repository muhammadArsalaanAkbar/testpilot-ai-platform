"""Local fixture-page test server (T133, contracts/browser-automation-adapter.md
Testing contract): serves tests/fixtures/fixture_site/ so engine tests can
exercise real navigation/interaction against known, stable markup instead of
a third-party site (avoids the flakiness of depending on an external site's
uptime/markup stability — see test_playwright_engine.py's own precedent).

This is infrastructure, not a test module itself — pytest never collects it
as tests (no `test_*` names), only imports its fixture.
"""

import http.server
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest

FIXTURE_SITE_DIR = Path(__file__).parent / "fixture_site"


class _FixtureSiteHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, directory=str(FIXTURE_SITE_DIR), **kwargs)  # type: ignore[arg-type]

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        pass


@pytest.fixture(scope="module")
def fixture_site_url() -> Iterator[str]:
    server = http.server.HTTPServer(("127.0.0.1", 0), _FixtureSiteHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()
    thread.join(timeout=5)
