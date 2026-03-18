"""Pydantic request / response models for the REST API."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


# ------------------------------------------------------------------
# Scan request / response
# ------------------------------------------------------------------

class ScanRequest(BaseModel):
    """Request body for ``POST /api/v1/scans``."""

    path: str = Field(..., description="Root directory to scan")
    engines: list[str] = Field(
        default=["regex"],
        description="Detection engines to use (regex, gliner, spacy, pydantic-ai, vector)",
    )
    profile: Optional[str] = Field(
        None, description="Scan profile (quick, standard, deep, gdpr-audit, ci)"
    )
    deduplicate: bool = Field(False, description="Remove duplicate findings")
    incremental: bool = Field(False, description="Skip unchanged files")
    text_chunk_size: int = Field(0, description="Text chunk size for NER (0 = disabled)")
    min_confidence: float = Field(0.0, description="Minimum confidence threshold")
    context_chars: int = Field(0, description="Context chars around findings")


class ScanResponse(BaseModel):
    """Response for scan creation."""

    session_id: str
    status: str = "running"
    message: str = "Scan started"


class ScanStatusResponse(BaseModel):
    """Response for scan status queries."""

    session_id: str
    status: str
    total_files: int = 0
    files_processed: int = 0
    total_matches: int = 0
    total_errors: int = 0
    duration_sec: Optional[float] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None


# ------------------------------------------------------------------
# Pagination
# ------------------------------------------------------------------

class PaginatedResponse(BaseModel):
    """Base model for paginated responses."""

    total: int = 0
    limit: int = 50
    offset: int = 0


class SessionListResponse(PaginatedResponse):
    """Paginated list of scan sessions."""

    sessions: list[dict[str, Any]] = Field(default_factory=list)


class FindingsResponse(PaginatedResponse):
    """Paginated list of findings."""

    findings: list[dict[str, Any]] = Field(default_factory=list)


# ------------------------------------------------------------------
# Analytics
# ------------------------------------------------------------------

class TrendEntry(BaseModel):
    """Single entry in a trend response."""

    period: str
    total_findings: int
    sessions: int = 0


class TypeDistribution(BaseModel):
    """PII type distribution entry."""

    pii_type: str
    count: int
    avg_confidence: Optional[float] = None


class SeverityEntry(BaseModel):
    """Severity breakdown entry."""

    severity: Optional[str]
    count: int


class EnginePerformance(BaseModel):
    """Engine performance entry."""

    engine: str
    total_matches: int = 0
    total_files: int = 0
    avg_processing_time: Optional[float] = None
    total_errors: int = 0


class DashboardSummary(BaseModel):
    """Aggregated dashboard summary."""

    total_sessions: int = 0
    completed_sessions: int = 0
    total_findings: int = 0
    unique_files_with_findings: int = 0
    recent_sessions: list[dict[str, Any]] = Field(default_factory=list)
    top_pii_types: list[dict[str, Any]] = Field(default_factory=list)
    severity_overview: dict[str, int] = Field(default_factory=dict)


# ------------------------------------------------------------------
# System
# ------------------------------------------------------------------

class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "ok"
    version: str = "1.0.0"


class EngineInfo(BaseModel):
    """Information about an available engine."""

    name: str
    available: bool
    description: str = ""
