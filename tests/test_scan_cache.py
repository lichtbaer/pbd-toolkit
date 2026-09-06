"""Tests for the incremental scan cache (core/scan_cache.py).

The cache decides whether a file is skipped on the next ``--incremental`` run,
so a wrong "unchanged" answer silently hides PII. These tests pin the
invalidation contract: mtime *and* size must match, and then the SHA-256
digest must match too.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import threading
import time

import pytest

from core.scan_cache import ScanCache, _sha256


class _ListHandler(logging.Handler):
    """Collects records directly; independent of propagation/caplog state."""

    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


@pytest.fixture
def log():
    """A private logger with an attached list handler.

    Other tests configure the logging tree (handlers, propagate=False), so
    relying on caplog made these tests order-dependent. An explicit logger
    passed to ScanCache sidesteps that.
    """
    logger = logging.getLogger(f"test.scan_cache.{id(object())}")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    handler = _ListHandler()
    handler.logger = logger  # type: ignore[attr-defined]
    logger.addHandler(handler)
    yield handler
    logger.removeHandler(handler)


@pytest.fixture
def cache(tmp_path, log):
    c = ScanCache(cache_path=str(tmp_path / "cache" / "scan.db"), logger=log.logger)
    yield c
    c.close()


def _touch(path, content: bytes, mtime: float | None = None) -> None:
    path.write_bytes(content)
    if mtime is not None:
        os.utime(path, (mtime, mtime))


class TestLifecycle:
    def test_creates_parent_directory_and_schema(self, tmp_path):
        db = tmp_path / "nested" / "dir" / "cache.db"
        c = ScanCache(cache_path=str(db))
        try:
            assert db.exists()
            with sqlite3.connect(db) as conn:
                tables = {
                    r[0]
                    for r in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                }
            assert "file_cache" in tables
            assert c.stats() == {"total_entries": 0}
        finally:
            c.close()

    def test_default_path_is_cwd_relative(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        c = ScanCache()
        try:
            assert (tmp_path / ".pbd_scan_cache.db").exists()
        finally:
            c.close()

    def test_close_is_idempotent_and_disables_cache(self, cache, tmp_path):
        f = tmp_path / "a.txt"
        _touch(f, b"x")
        cache.mark_scanned(str(f))
        cache.close()
        cache.close()
        assert cache.is_unchanged(str(f)) is False
        assert cache.stats() == {"total_entries": 0}

    def test_unopenable_database_degrades_to_no_cache(self, tmp_path, log):
        blocker = tmp_path / "not-a-dir"
        blocker.write_text("file, not a directory")
        c = ScanCache(cache_path=str(blocker / "cache.db"), logger=log.logger)
        try:
            assert c._conn is None
            assert any("failed to open cache" in m for m in log.messages)
            f = tmp_path / "a.txt"
            _touch(f, b"x")
            c.mark_scanned(str(f))  # no-op, must not raise
            assert c.is_unchanged(str(f)) is False
            c.clear()
            assert c.stats() == {"total_entries": 0}
        finally:
            c.close()


class TestInvalidation:
    def test_unknown_file_is_not_unchanged(self, cache, tmp_path):
        f = tmp_path / "a.txt"
        _touch(f, b"hello")
        assert cache.is_unchanged(str(f)) is False

    def test_marked_file_is_unchanged_until_content_changes(self, cache, tmp_path):
        f = tmp_path / "a.txt"
        _touch(f, b"hello", mtime=1_700_000_000)
        cache.mark_scanned(str(f))
        assert cache.is_unchanged(str(f)) is True
        assert cache.stats() == {"total_entries": 1}

        # Same size, same mtime, different content: only the hash can catch it.
        _touch(f, b"HELLO", mtime=1_700_000_000)
        assert cache.is_unchanged(str(f)) is False

    def test_mtime_change_alone_invalidates(self, cache, tmp_path):
        f = tmp_path / "a.txt"
        _touch(f, b"hello", mtime=1_700_000_000)
        cache.mark_scanned(str(f))
        os.utime(f, (1_700_000_001, 1_700_000_001))
        assert cache.is_unchanged(str(f)) is False

    def test_size_change_invalidates(self, cache, tmp_path):
        f = tmp_path / "a.txt"
        _touch(f, b"hello", mtime=1_700_000_000)
        cache.mark_scanned(str(f))
        _touch(f, b"hello!", mtime=1_700_000_000)
        assert cache.is_unchanged(str(f)) is False

    def test_rescan_after_change_updates_entry(self, cache, tmp_path):
        f = tmp_path / "a.txt"
        _touch(f, b"v1")
        cache.mark_scanned(str(f))
        _touch(f, b"v2-longer")
        assert cache.is_unchanged(str(f)) is False
        cache.mark_scanned(str(f))
        assert cache.is_unchanged(str(f)) is True
        assert cache.stats() == {"total_entries": 1}  # replaced, not duplicated

    def test_deleted_file_is_not_unchanged(self, cache, tmp_path):
        f = tmp_path / "a.txt"
        _touch(f, b"x")
        cache.mark_scanned(str(f))
        f.unlink()
        assert cache.is_unchanged(str(f)) is False

    def test_mark_scanned_ignores_missing_or_unreadable_files(self, cache, tmp_path):
        cache.mark_scanned(str(tmp_path / "missing.txt"))
        assert cache.stats() == {"total_entries": 0}
        d = tmp_path / "dir"
        d.mkdir()
        cache.mark_scanned(str(d))  # stat works, hashing fails -> ignored
        assert cache.stats() == {"total_entries": 0}

    def test_clear_forces_full_rescan(self, cache, tmp_path):
        files = []
        for i in range(3):
            f = tmp_path / f"{i}.txt"
            _touch(f, b"x" * i)
            cache.mark_scanned(str(f))
            files.append(f)
        assert cache.stats() == {"total_entries": 3}
        cache.clear()
        assert cache.stats() == {"total_entries": 0}
        assert all(cache.is_unchanged(str(f)) is False for f in files)

    def test_persists_across_instances(self, tmp_path):
        db = str(tmp_path / "scan.db")
        f = tmp_path / "a.txt"
        _touch(f, b"persist")
        c1 = ScanCache(cache_path=db)
        c1.mark_scanned(str(f))
        c1.close()
        c2 = ScanCache(cache_path=db)
        try:
            assert c2.is_unchanged(str(f)) is True
        finally:
            c2.close()


class TestRobustness:
    def test_corrupt_database_file_does_not_crash(self, tmp_path, caplog):
        db = tmp_path / "corrupt.db"
        db.write_bytes(b"this is not sqlite" * 100)
        with caplog.at_level(logging.WARNING):
            c = ScanCache(cache_path=str(db))
        try:
            f = tmp_path / "a.txt"
            _touch(f, b"x")
            c.mark_scanned(str(f))
            assert c.is_unchanged(str(f)) is False
        finally:
            c.close()

    def test_lookup_error_is_treated_as_miss(self, cache, tmp_path, log):
        f = tmp_path / "a.txt"
        _touch(f, b"x")
        cache.mark_scanned(str(f))
        # Drop the table underneath the open connection.
        cache._conn.execute("DROP TABLE file_cache")
        cache._conn.commit()
        assert cache.is_unchanged(str(f)) is False
        assert any("lookup failed" in m for m in log.messages)
        cache.mark_scanned(str(f))  # write failure is logged, not raised
        assert cache.stats() == {"total_entries": 0}

    def test_sha256_helper(self, tmp_path):
        f = tmp_path / "a.txt"
        f.write_bytes(b"abc")
        assert (
            _sha256(str(f))
            == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
        )
        assert _sha256(str(tmp_path / "missing")) is None

    def test_concurrent_marks_are_serialised(self, cache, tmp_path):
        files = []
        for i in range(40):
            f = tmp_path / f"{i}.txt"
            _touch(f, f"file-{i}".encode())
            files.append(str(f))

        errors: list[BaseException] = []

        def worker(chunk):
            try:
                for path in chunk:
                    cache.mark_scanned(path)
                    assert cache.is_unchanged(path)
            except BaseException as exc:  # pragma: no cover - reported below
                errors.append(exc)

        threads = [
            threading.Thread(target=worker, args=(files[i::4],)) for i in range(4)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
        assert not errors
        assert cache.stats() == {"total_entries": 40}
        assert all(cache.is_unchanged(p) for p in files)

    def test_last_scan_timestamp_is_recorded(self, cache, tmp_path):
        f = tmp_path / "a.txt"
        _touch(f, b"x")
        before = time.time()
        cache.mark_scanned(str(f))
        row = cache._conn.execute(
            "SELECT last_scan FROM file_cache WHERE path = ?", (str(f),)
        ).fetchone()
        assert row is not None
        from datetime import datetime

        assert datetime.fromisoformat(row[0]).timestamp() >= before - 1
