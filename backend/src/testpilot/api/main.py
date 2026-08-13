from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi.errors import RateLimitExceeded

from testpilot.api.deps import limiter
from testpilot.api.v1 import (
    assistant,
    auth,
    billing,
    health,
    issues,
    notifications,
    organizations,
    projects,
    reports,
    testcases,
    testruns,
)
from testpilot.core.config import get_settings
from testpilot.core.exceptions import RateLimitedError, register_exception_handlers
from testpilot.core.logging import configure_logging
from testpilot.core.middleware import CorrelationIdMiddleware
from testpilot.core.observability import init_sentry


def _rate_limit_exceeded_handler(request: Request, exc: Exception) -> JSONResponse:
    # Matches the shared {"error": {...}} envelope (contracts/_conventions.md)
    # instead of slowapi's default response shape. slowapi raises its own
    # RateLimitExceeded (not a TestPilotError), so this handler is
    # registered separately from register_exception_handlers below, but
    # reuses RateLimitedError's code/status_code as the single source of
    # truth (T198) rather than a second hardcoded copy of "rate_limited"/429.
    return JSONResponse(
        status_code=RateLimitedError.status_code,
        content={"error": {"code": RateLimitedError.code, "message": "Too many requests", "details": {}}},
    )


def create_app() -> FastAPI:
    settings = get_settings()
    # NFR-009. Idempotent (replaces root's handlers, doesn't accumulate them
    # across repeated calls) — safe to call once per process in production
    # and once per test in the `client` fixture alike. Note for future test
    # authors: this does mean pytest's `caplog` fixture's handler gets
    # replaced too if a test creates the app after caplog attaches its own;
    # no current test uses caplog, so this isn't yet a real conflict.
    configure_logging()
    init_sentry()  # NFR-012. No-op unless SENTRY_DSN is configured.

    app = FastAPI(
        title="TestPilot AI API",
        version="0.1.0",
        docs_url="/docs" if settings.environment != "production" else None,
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # NFR-011: automatic per-route HTTP request count/latency metrics.
    # `.expose(app)` is deliberately not called — `/metrics` is served by
    # api/v1/health.py instead, alongside the custom queue-depth collector,
    # so both live under the same router/prefix convention as /healthz and
    # /readyz rather than a second, differently-routed endpoint.
    Instrumentator().instrument(app)

    register_exception_handlers(app)

    app.include_router(health.router, prefix="/api/v1")
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(organizations.router, prefix="/api/v1")
    app.include_router(billing.router, prefix="/api/v1")
    app.include_router(projects.router, prefix="/api/v1")
    app.include_router(testcases.router, prefix="/api/v1")
    app.include_router(testruns.router, prefix="/api/v1")
    app.include_router(issues.router, prefix="/api/v1")
    app.include_router(assistant.router, prefix="/api/v1")
    app.include_router(reports.router, prefix="/api/v1")
    app.include_router(reports.org_router, prefix="/api/v1")
    app.include_router(notifications.router, prefix="/api/v1")

    return app


app = create_app()
