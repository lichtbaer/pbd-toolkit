"""SQLite-backed scan cache for incremental PII scanning.

When incremental mode is enabled (``--incremental``), each processed file's
SHA-256 hash and modification time are stored in a local SQLite database.  On
subsequent runs the scanner skips files whose hash and mtime haven't changed,
so only new or modified files are analysed.

Cache invalidation strategy
---------------------------
A file is considered **unchanged** when *both* of the following conditions hold:

1. The SHA-256 digest of the file content is identical to the cached digest.
2. The file's modification time (mtime) has not changed since the last scan.

The mtime pre-check avoids hashing large files that clearly haven't been
touched.  The hash provides a reliable content-based check that catches
in-place rewrites that preserve the mtime.

Thread safety
-------------
``ScanCache`` uses a per-instance ``threading.Lock`` to serialise SQLite
writes.  SQLite's WAL mode is enabled so multiple readers can operate
concurrently.  Each ``ScanCache`` instance should be created once and shared
across worker threads – don't create one instance per worker.
"""

from __future__ import annotations

import hashlib
import logging
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path


_DEFAULT_CACHE_FILENAME = ".pbd_scan_cache.db"
_SCHEMA = """
CREATE TABLE IF NOT EXISTS file_cache (
    path        TEXT PRIMARY KEY,
    sha256      TEXT NOT NULL,
    mtime       REAL NOT NULL,
    size        INTEGER NOT NULL,
    last_scan   TEXT NOT NULL
);
"""


class ScanCache:
    """Persistent cache that tracks which files have already been scanned.

    Usage::

        cache = ScanCache(cache_path="/path/to/cache.db")
        if cache.is_unchanged(file_path):
            return  # skip – already scanned, content unchanged
        # … process file …
        cache.mark_scanned(file_path)
        cache.close()
    """

    def __init__(self, cache_path: str | None = None, logger: logging.Logger | None = None):
        """Initialise the scan cache.

        Args:
            cache_path: Path to the SQLite database file.  Defaults to
                ``.pbd_scan_cache.db`` in the current working directory.
            logger: Optional logger for diagnostic messages.
        """
        self._path = cache_path or _DEFAULT_CACHE_FILENAME
        self._logger = logger or logging.getLogger(__name__)
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection | None = None
        self._open()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _open(self) -> None:
        """Open (or create) the SQLite database and ensure the schema exists."""
        try:
            Path(self._path).parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self._path, check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute(_SCHEMA)
            conn.commit()
            self._conn = conn
        except Exception as exc:
            self._logger.warning(f"ScanCache: failed to open cache at '{self._path}': {exc}")
            self._conn = None

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
    # Public API
    # ------------------------------------------------------------------

    def is_unchanged(self, file_path: str) -> bool:
        """Return True if *file_path* is cached and its content has not changed.

        A file is considered unchanged when its mtime **and** SHA-256 digest
        both match the cached values.  If the cache is unavailable (connection
        error, missing database) the method returns ``False`` so the file is
        processed normally.

        Args:
            file_path: Absolute or relative path to the file.

        Returns:
            ``True`` if the file can safely be skipped, ``False`` otherwise.
        """
        if self._conn is None:
            return False

        try:
            stat = os.stat(file_path)
        except OSError:
            return False

        try:
            with self._lock:
                cur = self._conn.execute(
                    "SELECT sha256, mtime, size FROM file_cache WHERE path = ?",
                    (file_path,),
                )
                row = cur.fetchone()
        except Exception as exc:
            self._logger.debug(f"ScanCache lookup failed for '{file_path}': {exc}")
            return False

        if row is None:
            return False  # not cached yet

        cached_hash, cached_mtime, cached_size = row

        # Fast pre-check: mtime or size changed → definitely modified
        if stat.st_mtime != cached_mtime or stat.st_size != cached_size:
            return False

        # Content-level check: hash the file
        current_hash = _sha256(file_path)
        return current_hash is not None and current_hash == cached_hash

    def mark_scanned(self, file_path: str) -> None:
        """Record that *file_path* has been successfully scanned.

        Inserts or replaces the cache entry with the file's current mtime,
        size and SHA-256 digest.

        Args:
            file_path: Path to the file that was scanned.
        """
        if self._conn is None:
            return

        try:
            stat = os.stat(file_path)
        except OSError as exc:
            self._logger.debug(f"ScanCache: cannot stat '{file_path}': {exc}")
            return

        digest = _sha256(file_path)
        if digest is None:
            return

        now = datetime.now(timezone.utc).isoformat()
        try:
            with self._lock:
                self._conn.execute(
                    """INSERT OR REPLACE INTO file_cache
                       (path, sha256, mtime, size, last_scan)
                       VALUES (?, ?, ?, ?, ?)""",
                    (file_path, digest, stat.st_mtime, stat.st_size, now),
                )
                self._conn.commit()
        except Exception as exc:
            self._logger.debug(f"ScanCache: write failed for '{file_path}': {exc}")

    def clear(self) -> None:
        """Delete all cached entries (full re-scan on next run)."""
        if self._conn is None:
            return
        try:
            with self._lock:
                self._conn.execute("DELETE FROM file_cache")
                self._conn.commit()
        except Exception as exc:
            self._logger.warning(f"ScanCache: clear failed: {exc}")

    def stats(self) -> dict[str, int]:
        """Return basic statistics about the cache contents.

        Returns:
            Dict with keys ``total_entries``.
        """
        if self._conn is None:
            return {"total_entries": 0}
        try:
            with self._lock:
                cur = self._conn.execute("SELECT COUNT(*) FROM file_cache")
                count = cur.fetchone()[0]
            return {"total_entries": count}
        except Exception:
            return {"total_entries": 0}


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _sha256(file_path: str, chunk_size: int = 65536) -> str | None:
    """Return the SHA-256 hex digest of *file_path*, or None on error."""
    h = hashlib.sha256()
    try:
        with open(file_path, "rb") as fh:
            while True:
                chunk = fh.read(chunk_size)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None
