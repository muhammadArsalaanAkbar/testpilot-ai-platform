"""Shared pagination helper (contracts/_conventions.md, T197): "list
endpoints accept `?page=1&page_size=25` (default 25, max 100)". This is the
single place those bounds/defaults live, and the single place offset/limit
arithmetic is computed, so no endpoint reimplements either.

Response shape is deliberately NOT standardized here — several contracts
(issues-api.md, reports-api.md, notifications-api.md) explicitly narrow the
general `{items, page, page_size, total}` envelope down to a bare
`{items: [...]}` (or add their own fields, e.g. notifications' unread_count)
while others (test-cases-api.md, test-runs-api.md) use the fuller shape —
each route's own `response_model` still owns that.
"""

from fastapi import Query

DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100


class PaginationParams:
    """FastAPI dependency: one canonical `?page=&page_size=` declaration
    (bounds, defaults, and the offset/limit arithmetic) shared by every
    paginated list endpoint, instead of each route re-declaring
    `Query(1, ge=1)`/`Query(25, ge=1, le=100)` independently."""

    def __init__(
        self,
        page: int = Query(1, ge=1, description="1-indexed page number."),
        page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="Items per page (max 100)."),
    ) -> None:
        self.page = page
        self.page_size = page_size

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size
