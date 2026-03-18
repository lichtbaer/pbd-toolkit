"""FastAPI application factory for the PBD Toolkit REST API."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from analytics.database import AnalyticsDatabase
from analytics.queries import AnalyticsQueries
from analytics.store import AnalyticsStore
from api.scanner_service import ScannerService

logger = logging.getLogger(__name__)


def create_app(
    analytics_db_path: str = ".pbd_analytics.db",
    cors_origins: Optional[list[str]] = None,
) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        analytics_db_path: Path to the SQLite analytics database.
        cors_origins: Allowed CORS origins (default: ``["*"]`` for local
            development – restrict in production).
    """
    app = FastAPI(
        title="PBD Toolkit API",
        description="REST API for PII scanning and analytics",
        version="1.0.0",
    )

    # CORS – allow React dev server by default
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Shared state --------------------------------------------------------
    db = AnalyticsDatabase(db_path=analytics_db_path)
    store = AnalyticsStore(db_path=analytics_db_path)
    queries = AnalyticsQueries(db=db)
    scanner_service = ScannerService(analytics_store=store)

    # Make these accessible to route handlers via app.state
    app.state.analytics_db = db
    app.state.analytics_store = store
    app.state.analytics_queries = queries
    app.state.scanner_service = scanner_service

    # Register routers ----------------------------------------------------
    from api.routes.scans import router as scans_router
    from api.routes.analytics import router as analytics_router
    from api.routes.system import router as system_router

    app.include_router(scans_router)
    app.include_router(analytics_router)
    app.include_router(system_router)

    @app.on_event("shutdown")
    def _shutdown() -> None:
        scanner_service.shutdown()
        store.close()
        db.close()

    return app
