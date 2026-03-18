"""Analytics query endpoints for dashboard consumption."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request

from api.models import DashboardSummary

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


@router.get("/dashboard", response_model=DashboardSummary)
def dashboard_summary(request: Request) -> DashboardSummary:
    """Aggregated dashboard summary across all sessions."""
    queries = request.app.state.analytics_queries
    data = queries.get_dashboard_summary()
    return DashboardSummary(**data)


@router.get("/trends")
def trends(
    request: Request,
    days: int = Query(30, ge=1, le=365),
    group_by: str = Query("day"),
) -> list[dict[str, Any]]:
    """Findings trend over time."""
    queries = request.app.state.analytics_queries
    return queries.get_trend_over_time(days=days, group_by=group_by)


@router.get("/types")
def pii_type_distribution(
    request: Request,
    session_id: str | None = Query(None),
) -> list[dict[str, Any]]:
    """PII type distribution (optionally scoped to a session)."""
    queries = request.app.state.analytics_queries
    return queries.get_pii_type_distribution(session_id=session_id)


@router.get("/severity")
def severity_breakdown(
    request: Request,
    session_id: str | None = Query(None),
) -> list[dict[str, Any]]:
    """Findings count by severity level."""
    queries = request.app.state.analytics_queries
    return queries.get_severity_breakdown(session_id=session_id)


@router.get("/engines")
def engine_performance(
    request: Request,
    session_id: str | None = Query(None),
) -> list[dict[str, Any]]:
    """Per-engine performance metrics."""
    queries = request.app.state.analytics_queries
    return queries.get_engine_performance(session_id=session_id)


@router.get("/file-types")
def file_type_analysis(
    request: Request,
    session_id: str | None = Query(None),
) -> list[dict[str, Any]]:
    """Analysis by file type."""
    queries = request.app.state.analytics_queries
    return queries.get_file_type_analysis(session_id=session_id)


@router.get("/dimensions")
def dimension_summary(
    request: Request,
    session_id: str | None = Query(None),
) -> list[dict[str, Any]]:
    """Findings aggregated by privacy dimension."""
    queries = request.app.state.analytics_queries
    return queries.get_dimension_summary(session_id=session_id)


@router.get("/top-files")
def top_affected_files(
    request: Request,
    session_id: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
) -> list[dict[str, Any]]:
    """Files with the most findings."""
    queries = request.app.state.analytics_queries
    return queries.get_top_affected_files(session_id=session_id, limit=limit)
