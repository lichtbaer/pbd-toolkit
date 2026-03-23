"""Predefined analytical queries for the analytics database.

These queries power the REST API analytics endpoints and can also be used
directly from Python for ad-hoc analysis.  All methods return plain
dictionaries / lists suitable for JSON serialisation.
"""

from __future__ import annotations

import logging
from typing import Any

from analytics.database import AnalyticsDatabase


class AnalyticsQueries:
    """Read-only query interface for the analytics database."""

    def __init__(
        self,
        db: AnalyticsDatabase,
        logger: logging.Logger | None = None,
    ) -> None:
        self._db = db
        self._logger = logger or logging.getLogger(__name__)

    # ------------------------------------------------------------------
    # Sessions
    # ------------------------------------------------------------------

    def get_sessions(
        self,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
    ) -> dict[str, Any]:
        """List scan sessions with pagination.

        Returns:
            ``{"sessions": [...], "total": int, "limit": int, "offset": int}``
        """
        conn = self._db.connection
        if conn is None:
            return {"sessions": [], "total": 0, "limit": limit, "offset": offset}

        where = ""
        params: list[Any] = []
        if status:
            where = "WHERE status = ?"
            params.append(status)

        with self._db.lock:
            cur = conn.execute(f"SELECT COUNT(*) FROM scan_sessions {where}", params)
            total = cur.fetchone()[0]

            cur = conn.execute(
                f"""SELECT * FROM scan_sessions {where}
                    ORDER BY started_at DESC LIMIT ? OFFSET ?""",
                params + [limit, offset],
            )
            rows = [dict(r) for r in cur.fetchall()]

        return {"sessions": rows, "total": total, "limit": limit, "offset": offset}

    def get_session_detail(self, session_id: str) -> dict[str, Any] | None:
        """Get full details for a single session including engine stats."""
        conn = self._db.connection
        if conn is None:
            return None

        with self._db.lock:
            cur = conn.execute(
                "SELECT * FROM scan_sessions WHERE id = ?", (session_id,)
            )
            row = cur.fetchone()
            if row is None:
                return None
            session = dict(row)

            cur = conn.execute(
                "SELECT * FROM engine_stats WHERE session_id = ?", (session_id,)
            )
            session["engine_stats"] = [dict(r) for r in cur.fetchall()]

            cur = conn.execute(
                "SELECT * FROM file_type_stats WHERE session_id = ?", (session_id,)
            )
            session["file_type_stats"] = [dict(r) for r in cur.fetchall()]

        return session

    def delete_session(self, session_id: str) -> bool:
        """Delete a session and all associated data.

        Returns:
            ``True`` if the session existed and was deleted.
        """
        conn = self._db.connection
        if conn is None:
            return False

        try:
            with self._db.lock:
                conn.execute("DELETE FROM findings WHERE session_id = ?", (session_id,))
                conn.execute(
                    "DELETE FROM engine_stats WHERE session_id = ?", (session_id,)
                )
                conn.execute(
                    "DELETE FROM file_type_stats WHERE session_id = ?", (session_id,)
                )
                cur = conn.execute(
                    "DELETE FROM scan_sessions WHERE id = ?", (session_id,)
                )
                conn.commit()
                return cur.rowcount > 0
        except Exception as exc:
            self._logger.debug("AnalyticsQueries: delete_session failed: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Findings
    # ------------------------------------------------------------------

    def get_findings(
        self,
        session_id: str | None = None,
        pii_type: str | None = None,
        severity: str | None = None,
        engine: str | None = None,
        dimension: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Query findings with optional filters and pagination."""
        conn = self._db.connection
        if conn is None:
            return {"findings": [], "total": 0, "limit": limit, "offset": offset}

        conditions: list[str] = []
        params: list[Any] = []

        if session_id:
            conditions.append("session_id = ?")
            params.append(session_id)
        if pii_type:
            conditions.append("pii_type = ?")
            params.append(pii_type)
        if severity:
            conditions.append("severity = ?")
            params.append(severity)
        if engine:
            conditions.append("engine = ?")
            params.append(engine)
        if dimension:
            conditions.append("dimension = ?")
            params.append(dimension)

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        with self._db.lock:
            cur = conn.execute(f"SELECT COUNT(*) FROM findings {where}", params)
            total = cur.fetchone()[0]

            cur = conn.execute(
                f"""SELECT * FROM findings {where}
                    ORDER BY created_at DESC LIMIT ? OFFSET ?""",
                params + [limit, offset],
            )
            rows = [dict(r) for r in cur.fetchall()]

        return {"findings": rows, "total": total, "limit": limit, "offset": offset}

    # ------------------------------------------------------------------
    # Analytical aggregations
    # ------------------------------------------------------------------

    def get_trend_over_time(
        self,
        days: int = 30,
        group_by: str = "day",
    ) -> list[dict[str, Any]]:
        """Get findings trend grouped by time period.

        Args:
            days: Number of days to look back.
            group_by: ``"day"`` or ``"week"`` or ``"month"``.
        """
        conn = self._db.connection
        if conn is None:
            return []

        date_format = {
            "day": "%Y-%m-%d",
            "week": "%Y-W%W",
            "month": "%Y-%m",
        }.get(group_by, "%Y-%m-%d")

        sql = f"""
            SELECT strftime('{date_format}', f.created_at) AS period,
                   COUNT(*) AS total_findings,
                   COUNT(DISTINCT f.session_id) AS sessions
            FROM findings f
            JOIN scan_sessions s ON f.session_id = s.id
            WHERE f.created_at >= datetime('now', ?)
            GROUP BY period
            ORDER BY period
        """

        with self._db.lock:
            cur = conn.execute(sql, (f"-{days} days",))
            return [dict(r) for r in cur.fetchall()]

    def get_pii_type_distribution(
        self, session_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Get distribution of PII types."""
        conn = self._db.connection
        if conn is None:
            return []

        where = ""
        params: list[Any] = []
        if session_id:
            where = "WHERE session_id = ?"
            params.append(session_id)

        sql = f"""
            SELECT pii_type, COUNT(*) AS count,
                   ROUND(AVG(confidence), 3) AS avg_confidence
            FROM findings {where}
            GROUP BY pii_type
            ORDER BY count DESC
        """

        with self._db.lock:
            cur = conn.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]

    def get_severity_breakdown(
        self, session_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Get findings count by severity level."""
        conn = self._db.connection
        if conn is None:
            return []

        where = ""
        params: list[Any] = []
        if session_id:
            where = "WHERE session_id = ?"
            params.append(session_id)

        sql = f"""
            SELECT severity, COUNT(*) AS count
            FROM findings {where}
            GROUP BY severity
            ORDER BY CASE severity
                WHEN 'CRITICAL' THEN 1
                WHEN 'HIGH' THEN 2
                WHEN 'MEDIUM' THEN 3
                WHEN 'LOW' THEN 4
                ELSE 5
            END
        """

        with self._db.lock:
            cur = conn.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]

    def get_engine_performance(
        self, session_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Get per-engine performance metrics."""
        conn = self._db.connection
        if conn is None:
            return []

        where = ""
        params: list[Any] = []
        if session_id:
            where = "WHERE session_id = ?"
            params.append(session_id)

        sql = f"""
            SELECT engine,
                   SUM(matches_found) AS total_matches,
                   SUM(files_processed) AS total_files,
                   ROUND(AVG(processing_time), 3) AS avg_processing_time,
                   SUM(errors) AS total_errors
            FROM engine_stats {where}
            GROUP BY engine
            ORDER BY total_matches DESC
        """

        with self._db.lock:
            cur = conn.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]

    def get_file_type_analysis(
        self, session_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Get analysis by file type."""
        conn = self._db.connection
        if conn is None:
            return []

        where = ""
        params: list[Any] = []
        if session_id:
            where = "WHERE session_id = ?"
            params.append(session_id)

        sql = f"""
            SELECT extension,
                   SUM(files_scanned) AS total_files,
                   SUM(matches_found) AS total_matches
            FROM file_type_stats {where}
            GROUP BY extension
            ORDER BY total_matches DESC
        """

        with self._db.lock:
            cur = conn.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]

    def get_dimension_summary(
        self, session_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Get findings aggregated by privacy dimension."""
        conn = self._db.connection
        if conn is None:
            return []

        where = ""
        params: list[Any] = []
        if session_id:
            where = "WHERE session_id = ?"
            params.append(session_id)

        sql = f"""
            SELECT dimension, COUNT(*) AS count,
                   COUNT(DISTINCT file_path) AS files_affected,
                   COUNT(DISTINCT engine) AS engines_involved
            FROM findings {where}
            GROUP BY dimension
            ORDER BY count DESC
        """

        with self._db.lock:
            cur = conn.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]

    def get_top_affected_files(
        self,
        session_id: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Get files with the most findings."""
        conn = self._db.connection
        if conn is None:
            return []

        where = ""
        params: list[Any] = []
        if session_id:
            where = "WHERE session_id = ?"
            params.append(session_id)

        sql = f"""
            SELECT file_path, COUNT(*) AS findings_count,
                   COUNT(DISTINCT pii_type) AS distinct_types,
                   COUNT(DISTINCT dimension) AS distinct_dimensions
            FROM findings {where}
            GROUP BY file_path
            ORDER BY findings_count DESC
            LIMIT ?
        """

        with self._db.lock:
            cur = conn.execute(sql, params + [limit])
            return [dict(r) for r in cur.fetchall()]

    def get_dashboard_summary(self) -> dict[str, Any]:
        """Get an aggregated dashboard summary across all sessions."""
        conn = self._db.connection
        if conn is None:
            return {}

        with self._db.lock:
            # Total sessions
            cur = conn.execute("SELECT COUNT(*) FROM scan_sessions")
            total_sessions = cur.fetchone()[0]

            # Completed sessions
            cur = conn.execute(
                "SELECT COUNT(*) FROM scan_sessions WHERE status = 'completed'"
            )
            completed_sessions = cur.fetchone()[0]

            # Total findings
            cur = conn.execute("SELECT COUNT(*) FROM findings")
            total_findings = cur.fetchone()[0]

            # Total unique files with findings
            cur = conn.execute("SELECT COUNT(DISTINCT file_path) FROM findings")
            unique_files = cur.fetchone()[0]

            # Recent sessions (last 5)
            cur = conn.execute(
                """SELECT id, started_at, status, scan_path, total_matches, duration_sec
                   FROM scan_sessions ORDER BY started_at DESC LIMIT 5"""
            )
            recent_sessions = [dict(r) for r in cur.fetchall()]

            # Top PII types
            cur = conn.execute(
                """SELECT pii_type, COUNT(*) AS count FROM findings
                   GROUP BY pii_type ORDER BY count DESC LIMIT 10"""
            )
            top_types = [dict(r) for r in cur.fetchall()]

            # Severity overview
            cur = conn.execute(
                """SELECT severity, COUNT(*) AS count FROM findings
                   GROUP BY severity"""
            )
            severity_overview = {r["severity"]: r["count"] for r in cur.fetchall()}

        return {
            "total_sessions": total_sessions,
            "completed_sessions": completed_sessions,
            "total_findings": total_findings,
            "unique_files_with_findings": unique_files,
            "recent_sessions": recent_sessions,
            "top_pii_types": top_types,
            "severity_overview": severity_overview,
        }
