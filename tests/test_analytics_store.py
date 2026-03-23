"""Tests for the analytics store module."""

import os

import pytest

from analytics.database import AnalyticsDatabase
from analytics.store import AnalyticsStore


@pytest.fixture
def tmp_db(tmp_path):
    """Provide a temporary database path."""
    return str(tmp_path / "test_analytics.db")


@pytest.fixture
def store(tmp_db):
    """Provide an AnalyticsStore with a temporary database."""
    s = AnalyticsStore(db_path=tmp_db)
    yield s
    s.close()


class TestAnalyticsDatabase:
    """Tests for the low-level database module."""

    def test_creates_db_file(self, tmp_db):
        db = AnalyticsDatabase(db_path=tmp_db)
        assert os.path.exists(tmp_db)
        db.close()

    def test_schema_version(self, tmp_db):
        db = AnalyticsDatabase(db_path=tmp_db)
        assert db.is_available
        cur = db.connection.execute("PRAGMA user_version;")
        version = cur.fetchone()[0]
        assert version == 1
        db.close()

    def test_tables_created(self, tmp_db):
        db = AnalyticsDatabase(db_path=tmp_db)
        cur = db.connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = {row[0] for row in cur.fetchall()}
        assert "scan_sessions" in tables
        assert "findings" in tables
        assert "engine_stats" in tables
        assert "file_type_stats" in tables
        db.close()

    def test_close_and_reopen(self, tmp_db):
        db = AnalyticsDatabase(db_path=tmp_db)
        db.close()
        assert not db.is_available
        # Re-open should work (idempotent schema)
        db2 = AnalyticsDatabase(db_path=tmp_db)
        assert db2.is_available
        db2.close()


class TestAnalyticsStore:
    """Tests for the high-level store."""

    def test_create_session(self, store):
        sid = store.create_session(
            scan_path="/data", config_summary={"engines": ["regex"]}
        )
        assert isinstance(sid, str)
        assert len(sid) == 32  # hex UUID

    def test_complete_session(self, store):
        sid = store.create_session(scan_path="/data")
        store.complete_session(
            session_id=sid,
            total_files=100,
            files_processed=95,
            total_matches=42,
            total_errors=5,
            duration_sec=12.5,
        )
        # Verify via raw query
        conn = store._db.connection
        cur = conn.execute(
            "SELECT status, total_matches FROM scan_sessions WHERE id = ?", (sid,)
        )
        row = cur.fetchone()
        assert row["status"] == "completed"
        assert row["total_matches"] == 42

    def test_fail_session(self, store):
        sid = store.create_session(scan_path="/data")
        store.fail_session(sid, "something broke")
        conn = store._db.connection
        cur = conn.execute("SELECT status FROM scan_sessions WHERE id = ?", (sid,))
        assert cur.fetchone()["status"] == "failed"

    def test_record_finding(self, store):
        sid = store.create_session(scan_path="/data")
        store.record_finding(
            session_id=sid,
            file_path="/data/file.pdf",
            pii_type="REGEX_EMAIL",
            engine="regex",
            severity="MEDIUM",
            confidence=0.95,
        )
        conn = store._db.connection
        cur = conn.execute("SELECT * FROM findings WHERE session_id = ?", (sid,))
        row = cur.fetchone()
        assert row["pii_type"] == "REGEX_EMAIL"
        assert row["engine"] == "regex"
        assert row["dimension"] == "contact_information"

    def test_record_finding_from_match(self, store):
        """Test duck-typed match recording."""

        class FakeMatch:
            file = "/data/test.txt"
            type = "REGEX_IBAN"
            engine = "regex"
            severity = "HIGH"
            ner_score = None

        sid = store.create_session(scan_path="/data")
        store.record_finding_from_match(sid, FakeMatch())
        conn = store._db.connection
        cur = conn.execute(
            "SELECT pii_type, dimension FROM findings WHERE session_id = ?", (sid,)
        )
        row = cur.fetchone()
        assert row["pii_type"] == "REGEX_IBAN"
        assert row["dimension"] == "financial"

    def test_record_engine_stats(self, store):
        sid = store.create_session(scan_path="/data")
        store.record_engine_stats(sid, "regex", matches_found=10, files_processed=50)
        conn = store._db.connection
        cur = conn.execute("SELECT * FROM engine_stats WHERE session_id = ?", (sid,))
        row = cur.fetchone()
        assert row["matches_found"] == 10

    def test_record_file_type_stats(self, store):
        sid = store.create_session(scan_path="/data")
        store.record_file_type_stats(sid, ".pdf", files_scanned=20, matches_found=5)
        conn = store._db.connection
        cur = conn.execute("SELECT * FROM file_type_stats WHERE session_id = ?", (sid,))
        row = cur.fetchone()
        assert row["extension"] == ".pdf"
        assert row["matches_found"] == 5

    def test_is_available(self, store):
        assert store.is_available

    def test_graceful_degradation_bad_path(self):
        """Store should not crash on invalid DB path."""
        s = AnalyticsStore(
            db_path="/nonexistent/dir/that/really/does/not/exist/db.sqlite"
        )
        # create_session should return an ID even if DB is unavailable
        sid = s.create_session(scan_path="/data")
        assert isinstance(sid, str)
        s.close()
