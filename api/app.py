"""FastAPI application factory for the PBD Toolkit REST API."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from analytics.database import AnalyticsDatabase
from analytics.queries import AnalyticsQueries
from analytics.store import AnalyticsStore
from api.middleware import APIKeyMiddleware, RateLimitMiddleware
from api.scanner_service import ScannerService

logger = logging.getLogger(__name__)

# Safe defaults for CORS origins (common local dev servers).
_DEFAULT_CORS_ORIGINS = ["http://localhost:3000", "http://localhost:8080"]

# Default number of worker threads for background scans (see ScannerService).
_DEFAULT_SCAN_WORKERS = 2


def _env_flag(name: str) -> bool:
    """Parse a boolean environment variable ("1", "true", "yes" -> True)."""
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


class UnauthenticatedAPIError(RuntimeError):
    """Raised when the API would start without authentication and no opt-out was given."""


def create_app(
    analytics_db_path: str = ".pbd_analytics.db",
    cors_origins: list[str] | None = None,
    api_key: str | None = None,
    allowed_scan_roots: list[str] | None = None,
    rate_limit: int = 60,
    scan_rate_limit: int = 5,
    allow_unauthenticated: bool = False,
    scan_workers: int | None = None,
) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        analytics_db_path: Path to the SQLite analytics database.
        cors_origins: Allowed CORS origins. Defaults to localhost dev ports.
        api_key: Optional API key for Bearer authentication.
        allowed_scan_roots: Directories the scan API is allowed to access.
        rate_limit: General requests-per-minute limit per client IP.
        scan_rate_limit: Scan-creation requests-per-minute limit per client IP.
        allow_unauthenticated: Explicit opt-out allowing the API to serve
            without an API key. Also settable via ``PBD_ALLOW_UNAUTHENTICATED``.
            Without this (or an API key), ``create_app`` refuses to start.
        scan_workers: Worker-thread count for background scans. Defaults to
            ``PBD_SCAN_WORKERS`` env var, then 2.

    Raises:
        UnauthenticatedAPIError: If no API key is configured and neither
            ``allow_unauthenticated`` nor ``PBD_ALLOW_UNAUTHENTICATED`` opts out.
    """
    # Resolve the API key from parameter or environment variable.
    effective_api_key = api_key or os.environ.get("PBD_API_KEY")
    effective_allow_unauthenticated = allow_unauthenticated or _env_flag(
        "PBD_ALLOW_UNAUTHENTICATED"
    )

    if not effective_api_key and not effective_allow_unauthenticated:
        raise UnauthenticatedAPIError(
            "Refusing to start the API without authentication: no API key was "
            "configured (--api-key / PBD_API_KEY). The API scans directories for "
            "PII and stores findings metadata, so running it unauthenticated is "
            "unsafe by default. Set an API key, or explicitly opt out with "
            "--allow-unauthenticated / PBD_ALLOW_UNAUTHENTICATED=1 if you understand "
            "the risk (e.g. a locked-down internal network)."
        )

    effective_scan_workers = scan_workers or int(
        os.environ.get("PBD_SCAN_WORKERS", _DEFAULT_SCAN_WORKERS)
    )

    # Shared state --------------------------------------------------------
    db = AnalyticsDatabase(db_path=analytics_db_path)
    store = AnalyticsStore(db_path=analytics_db_path)
    queries = AnalyticsQueries(db=db)
    scanner_service = ScannerService(
        analytics_store=store,
        allowed_scan_roots=allowed_scan_roots,
        max_workers=effective_scan_workers,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        scanner_service.shutdown()
        store.close()
        db.close()

    app = FastAPI(
        title="PBD Toolkit API",
        description="REST API for PII scanning and analytics",
        version="1.0.0",
        lifespan=lifespan,
    )

    # -- Security middleware (outermost first) -----------------------------

    if effective_api_key:
        app.add_middleware(APIKeyMiddleware, api_key=effective_api_key)
    else:
        logger.warning(
            "API is running WITHOUT authentication. "
            "Set --api-key or PBD_API_KEY to enable Bearer token auth."
        )

    # Rate limiting
    app.add_middleware(
        RateLimitMiddleware,
        requests_per_minute=rate_limit,
        scan_requests_per_minute=scan_rate_limit,
    )

    # CORS – use safe defaults instead of wildcard
    origins = cors_origins if cors_origins is not None else _DEFAULT_CORS_ORIGINS
    has_wildcard = "*" in origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=not has_wildcard,  # wildcard + credentials is a spec violation
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept"],
    )

    # Make shared services accessible to route handlers via app.state
    app.state.analytics_db = db
    app.state.analytics_store = store
    app.state.analytics_queries = queries
    app.state.scanner_service = scanner_service

    # Register routers ----------------------------------------------------
    from api.routes.analytics import router as analytics_router
    from api.routes.scans import router as scans_router
    from api.routes.system import router as system_router

    app.include_router(scans_router)
    app.include_router(analytics_router)
    app.include_router(system_router)

    return app
