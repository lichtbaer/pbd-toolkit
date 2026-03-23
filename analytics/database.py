"""SQLite database connection and schema management for analytics.

Follows the same patterns as ``core.scan_cache``: WAL mode, per-instance
threading lock, graceful degradation on errors.

Schema versioning uses ``PRAGMA user_version`` so that future migrations
can be applied automatically.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from pathlib import Path

_DEFAULT_DB_PATH = ".pbd_analytics.db"

# Current schema version – bump when adding migrations.
_SCHEMA_VERSION = 1

_SCHEMA_V1 = """
-- Scan sessions
CREATE TABLE IF NOT EXISTS scan_sessions (
    id              TEXT PRIMARY KEY,
    started_at      TEXT NOT NULL,
    finished_at     TEXT,
    status          TEXT NOT NULL DEFAULT 'running',
    scan_path       TEXT NOT NULL,
    total_files     INTEGER DEFAULT 0,
    files_processed INTEGER DEFAULT 0,
    total_matches   INTEGER DEFAULT 0,
    total_errors    INTEGER DEFAULT 0,
    duration_sec    REAL,
    config_summary  TEXT,
    source          TEXT DEFAULT 'cli'
);

-- Individual findings (NO PII text stored – privacy preserving)
CREATE TABLE IF NOT EXISTS findings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT NOT NULL,
    file_path       TEXT NOT NULL,
    pii_type        TEXT NOT NULL,
    engine          TEXT NOT NULL,
    severity        TEXT,
    confidence      REAL,
    dimension       TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (session_id) REFERENCES scan_sessions(id)
);

-- Per-engine statistics per session
CREATE TABLE IF NOT EXISTS engine_stats (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT NOT NULL,
    engine          TEXT NOT NULL,
    matches_found   INTEGER DEFAULT 0,
    files_processed INTEGER DEFAULT 0,
    processing_time REAL,
    errors          INTEGER DEFAULT 0,
    UNIQUE(session_id, engine),
    FOREIGN KEY (session_id) REFERENCES scan_sessions(id)
);

-- Per-file-type statistics per session
CREATE TABLE IF NOT EXISTS file_type_stats (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT NOT NULL,
    extension       TEXT NOT NULL,
    files_scanned   INTEGER DEFAULT 0,
    matches_found   INTEGER DEFAULT 0,
    UNIQUE(session_id, extension),
    FOREIGN KEY (session_id) REFERENCES scan_sessions(id)
);

-- Analytical indices
CREATE INDEX IF NOT EXISTS idx_findings_session   ON findings(session_id);
CREATE INDEX IF NOT EXISTS idx_findings_type       ON findings(pii_type);
CREATE INDEX IF NOT EXISTS idx_findings_severity   ON findings(severity);
CREATE INDEX IF NOT EXISTS idx_findings_dimension  ON findings(dimension);
CREATE INDEX IF NOT EXISTS idx_findings_engine     ON findings(engine);
CREATE INDEX IF NOT EXISTS idx_sessions_started    ON scan_sessions(started_at);
CREATE INDEX IF NOT EXISTS idx_sessions_status     ON scan_sessions(status);
"""


class AnalyticsDatabase:
    """Low-level SQLite connection manager for the analytics database.

    This class handles connection lifecycle, schema creation and future
    migrations.  Higher-level store / query classes should use this to
    obtain a connection.
    """

    def __init__(
        self,
        db_path: str | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._path = db_path or _DEFAULT_DB_PATH
        self._logger = logger or logging.getLogger(__name__)
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection | None = None
        self._open()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _open(self) -> None:
        """Open the database and ensure the schema is up to date."""
        try:
            Path(self._path).parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self._path, check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA foreign_keys=ON;")
            conn.row_factory = sqlite3.Row
            self._conn = conn
            self._apply_migrations()
        except Exception as exc:
            self._logger.warning(
                "AnalyticsDatabase: failed to open '%s': %s", self._path, exc
            )
            self._conn = None

    def _apply_migrations(self) -> None:
        """Apply schema migrations based on ``PRAGMA user_version``."""
        if self._conn is None:
            return

        cur = self._conn.execute("PRAGMA user_version;")
        current_version = cur.fetchone()[0]

        if current_version < 1:
            self._conn.executescript(_SCHEMA_V1)
            self._conn.execute(f"PRAGMA user_version = {_SCHEMA_VERSION};")
            self._conn.commit()
            self._logger.debug("AnalyticsDatabase: applied schema v%d", _SCHEMA_VERSION)

    def close(self) -> None:
        """Close the database connection."""
        with self._lock:
            if self._conn:
                try:
                    self._conn.close()
                except Exception:
                    pass
                self._conn = None

    # ------------------------------------------------------------------
    # Access
    # ------------------------------------------------------------------

    @property
    def connection(self) -> sqlite3.Connection | None:
        """Return the underlying SQLite connection (may be ``None``)."""
        return self._conn

    @property
    def lock(self) -> threading.Lock:
        """Return the instance lock for external synchronisation."""
        return self._lock

    @property
    def is_available(self) -> bool:
        """Return ``True`` if the database connection is open."""
        return self._conn is not None
