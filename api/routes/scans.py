"""Scan management endpoints."""

from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException, Query, Request

from api.models import (
    FindingsResponse,
    ScanRequest,
    ScanResponse,
    ScanStatusResponse,
    SessionListResponse,
)

router = APIRouter(prefix="/api/v1/scans", tags=["scans"])

_SESSION_ID_RE = re.compile(r"^[0-9a-f]{32}$")


def _validate_session_id(session_id: str) -> str:
    """Validate that session_id is a hex UUID4 (32 hex chars)."""
    if not _SESSION_ID_RE.match(session_id):
        raise HTTPException(status_code=400, detail="Invalid session_id format")
    return session_id


@router.post("", response_model=ScanResponse, status_code=202)
def create_scan(body: ScanRequest, request: Request) -> ScanResponse:
    """Start a new PII scan in the background."""
    service = request.app.state.scanner_service

    try:
        session_id = service.start_scan(
            path=body.path,
            engines=body.engines,
            profile=body.profile,
            deduplicate=body.deduplicate,
            incremental=body.incremental,
            text_chunk_size=body.text_chunk_size,
            min_confidence=body.min_confidence,
            context_chars=body.context_chars,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return ScanResponse(session_id=session_id, status="running", message="Scan started")


@router.get("", response_model=SessionListResponse)
def list_scans(
    request: Request,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    status: str | None = Query(None),
) -> SessionListResponse:
    """List scan sessions with optional status filter."""
    queries = request.app.state.analytics_queries
    result = queries.get_sessions(limit=limit, offset=offset, status=status)
    return SessionListResponse(**result)


@router.get("/{session_id}", response_model=ScanStatusResponse)
def get_scan(session_id: str, request: Request) -> ScanStatusResponse:
    """Get details and status of a single scan."""
    _validate_session_id(session_id)
    queries = request.app.state.analytics_queries
    detail = queries.get_session_detail(session_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return ScanStatusResponse(
        session_id=detail["id"],
        status=detail["status"],
        total_files=detail.get("total_files", 0) or 0,
        files_processed=detail.get("files_processed", 0) or 0,
        total_matches=detail.get("total_matches", 0) or 0,
        total_errors=detail.get("total_errors", 0) or 0,
        duration_sec=detail.get("duration_sec"),
        started_at=detail.get("started_at"),
        finished_at=detail.get("finished_at"),
    )


@router.get("/{session_id}/findings", response_model=FindingsResponse)
def get_scan_findings(
    session_id: str,
    request: Request,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    pii_type: str | None = Query(None),
    severity: str | None = Query(None),
    engine: str | None = Query(None),
    dimension: str | None = Query(None),
) -> FindingsResponse:
    """Get findings for a specific scan session."""
    _validate_session_id(session_id)
    queries = request.app.state.analytics_queries
    result = queries.get_findings(
        session_id=session_id,
        pii_type=pii_type,
        severity=severity,
        engine=engine,
        dimension=dimension,
        limit=limit,
        offset=offset,
    )
    return FindingsResponse(**result)


@router.delete("/{session_id}", status_code=204)
def delete_scan(session_id: str, request: Request) -> None:
    """Delete a scan session and all associated data."""
    _validate_session_id(session_id)
    queries = request.app.state.analytics_queries
    deleted = queries.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
