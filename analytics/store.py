"""High-level analytics store for recording scan sessions and findings.

Privacy note: this store does **not** persist the actual PII text that was
detected.  Only metadata (type, file path, engine, severity, confidence,
privacy dimension) is stored.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from analytics.database import AnalyticsDatabase
from core.privacy_dimensions import get_dimension


class AnalyticsStore:
    """Persistent store for scan sessions and their findings.

    Thread-safe – uses the underlying ``AnalyticsDatabase`` lock for all
    write operations.

    Usage::

        store = AnalyticsStore(db_path=".pbd_analytics.db")
        sid = store.create_session("/data", {"engines": ["regex"]})
        store.record_finding(sid, pii_match)
        store.complete_session(sid, statistics)
        store.close()
    """

    def __init__(
        self,
        db_path: str | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._db = AnalyticsDatabase(db_path=db_path, logger=logger)
        self._logger = logger or logging.getLogger(__name__)

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def create_session(
        self,
        scan_path: str,
        config_summary: dict[str, Any] | None = None,
        source: str = "cli",
    ) -> str:
        """Create a new scan session and return its ID.

        Args:
            scan_path: Root path being scanned.
            config_summary: Optional dict describing the scan configuration
                (engines, profile, options).  Serialised as JSON.
            source: Origin of the scan – ``"cli"`` or ``"api"``.

        Returns:
            UUID string identifying the session.
        """
        session_id = uuid.uuid4().hex
        now = datetime.now(timezone.utc).isoformat()
        config_json = json.dumps(config_summary, default=str) if config_summary else None

        conn = self._db.connection
        if conn is None:
            return session_id

        try:
            with self._db.lock:
                conn.execute(
                    """INSERT INTO scan_sessions
                       (id, started_at, status, scan_path, config_summary, source)
                       VALUES (?, ?, 'running', ?, ?, ?)""",
                    (session_id, now, scan_path, config_json, source),
                )
                conn.commit()
        except Exception as exc:
            self._logger.warning("AnalyticsStore: create_session failed: %s", exc)

        return session_id

    def complete_session(
        self,
        session_id: str,
        total_files: int = 0,
        files_processed: int = 0,
        total_matches: int = 0,
        total_errors: int = 0,
        duration_sec: float = 0.0,
    ) -> None:
        """Mark a session as completed and record final statistics."""
        conn = self._db.connection
        if conn is None:
            return

        now = datetime.now(timezone.utc).isoformat()
        try:
            with self._db.lock:
                conn.execute(
                    """UPDATE scan_sessions
                       SET finished_at = ?, status = 'completed',
                           total_files = ?, files_processed = ?,
                           total_matches = ?, total_errors = ?,
                           duration_sec = ?
                       WHERE id = ?""",
                    (
                        now,
                        total_files,
                        files_processed,
                        total_matches,
                        total_errors,
                        duration_sec,
                        session_id,
                    ),
                )
                conn.commit()
        except Exception as exc:
            self._logger.warning("AnalyticsStore: complete_session failed: %s", exc)

    def fail_session(self, session_id: str, error_msg: str | None = None) -> None:
        """Mark a session as failed."""
        conn = self._db.connection
        if conn is None:
            return

        now = datetime.now(timezone.utc).isoformat()
        try:
            with self._db.lock:
                conn.execute(
                    """UPDATE scan_sessions
                       SET finished_at = ?, status = 'failed'
                       WHERE id = ?""",
                    (now, session_id),
                )
                conn.commit()
        except Exception as exc:
            self._logger.warning("AnalyticsStore: fail_session failed: %s", exc)

    # ------------------------------------------------------------------
    # Finding recording
    # ------------------------------------------------------------------

    def record_finding(
        self,
        session_id: str,
        file_path: str,
        pii_type: str,
        engine: str,
        severity: str | None = None,
        confidence: float | None = None,
    ) -> None:
        """Record a single PII finding (metadata only, no PII text).

        Args:
            session_id: Session this finding belongs to.
            file_path: Path of the file where PII was detected.
            pii_type: Detection type label (e.g. ``"REGEX_EMAIL"``).
            engine: Name of the engine that detected it.
            severity: Severity classification (``LOW`` / ``MEDIUM`` / ``HIGH`` / ``CRITICAL``).
            confidence: Confidence score (0.0 – 1.0), if available.
        """
        conn = self._db.connection
        if conn is None:
            return

        dimension = get_dimension(pii_type)

        try:
            with self._db.lock:
                conn.execute(
                    """INSERT INTO findings
                       (session_id, file_path, pii_type, engine, severity, confidence, dimension)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (session_id, file_path, pii_type, engine, severity, confidence, dimension),
                )
                conn.commit()
        except Exception as exc:
            self._logger.warning("AnalyticsStore: record_finding failed: %s", exc)

    def record_finding_from_match(self, session_id: str, match: Any) -> None:
        """Convenience wrapper that accepts a ``PiiMatch`` object.

        This avoids importing ``matches.PiiMatch`` directly (which would
        create a circular dependency) by duck-typing the match object.
        """
        self.record_finding(
            session_id=session_id,
            file_path=getattr(match, "file", ""),
            pii_type=getattr(match, "type", ""),
            engine=getattr(match, "engine", "") or "unknown",
            severity=getattr(match, "severity", None),
            confidence=getattr(match, "ner_score", None),
        )

    # ------------------------------------------------------------------
    # Engine / file-type statistics
    # ------------------------------------------------------------------

    def record_engine_stats(
        self,
        session_id: str,
        engine: str,
        matches_found: int = 0,
        files_processed: int = 0,
        processing_time: float | None = None,
        errors: int = 0,
    ) -> None:
        """Record per-engine statistics for a session."""
        conn = self._db.connection
        if conn is None:
            return

        try:
            with self._db.lock:
                conn.execute(
                    """INSERT OR REPLACE INTO engine_stats
                       (session_id, engine, matches_found, files_processed, processing_time, errors)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (session_id, engine, matches_found, files_processed, processing_time, errors),
                )
                conn.commit()
        except Exception as exc:
            self._logger.warning("AnalyticsStore: record_engine_stats failed: %s", exc)

    def record_file_type_stats(
        self,
        session_id: str,
        extension: str,
        files_scanned: int = 0,
        matches_found: int = 0,
    ) -> None:
        """Record per-file-type statistics for a session."""
        conn = self._db.connection
        if conn is None:
            return

        try:
            with self._db.lock:
                conn.execute(
                    """INSERT OR REPLACE INTO file_type_stats
                       (session_id, extension, files_scanned, matches_found)
                       VALUES (?, ?, ?, ?)""",
                    (session_id, extension, files_scanned, matches_found),
                )
                conn.commit()
        except Exception as exc:
            self._logger.warning("AnalyticsStore: record_file_type_stats failed: %s", exc)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the underlying database connection."""
        self._db.close()

    @property
    def is_available(self) -> bool:
        """Return ``True`` when the database is usable."""
        return self._db.is_available
