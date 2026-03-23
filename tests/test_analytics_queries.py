"""Tests for the analytics query module."""

import pytest

from analytics.database import AnalyticsDatabase
from analytics.queries import AnalyticsQueries
from analytics.store import AnalyticsStore


@pytest.fixture
def db_and_store(tmp_path):
    """Provide a database, store, and queries instance with seed data."""
    db_path = str(tmp_path / "test_analytics.db")
    db = AnalyticsDatabase(db_path=db_path)
    store = AnalyticsStore(db_path=db_path)
    queries = AnalyticsQueries(db=db)

    # Seed data: two sessions with findings
    sid1 = store.create_session(
        scan_path="/data/project1", config_summary={"engines": ["regex"]}
    )
    store.record_finding(
        sid1, "/data/project1/a.pdf", "REGEX_EMAIL", "regex", "MEDIUM", 0.9
    )
    store.record_finding(
        sid1, "/data/project1/a.pdf", "REGEX_IBAN", "regex", "HIGH", 0.95
    )
    store.record_finding(
        sid1, "/data/project1/b.docx", "REGEX_PHONE", "regex", "LOW", 0.8
    )
    store.record_engine_stats(sid1, "regex", matches_found=3, files_processed=10)
    store.record_file_type_stats(sid1, ".pdf", files_scanned=5, matches_found=2)
    store.record_file_type_stats(sid1, ".docx", files_scanned=5, matches_found=1)
    store.complete_session(
        sid1, total_files=10, files_processed=10, total_matches=3, duration_sec=2.5
    )

    sid2 = store.create_session(
        scan_path="/data/project2", config_summary={"engines": ["regex", "gliner"]}
    )
    store.record_finding(
        sid2, "/data/project2/c.txt", "REGEX_EMAIL", "regex", "MEDIUM", 0.85
    )
    store.record_finding(
        sid2, "/data/project2/c.txt", "NER_PERSON", "gliner", "HIGH", 0.7
    )
    store.record_engine_stats(sid2, "regex", matches_found=1, files_processed=5)
    store.record_engine_stats(sid2, "gliner", matches_found=1, files_processed=5)
    store.complete_session(
        sid2, total_files=5, files_processed=5, total_matches=2, duration_sec=1.0
    )

    yield {"db": db, "store": store, "queries": queries, "sid1": sid1, "sid2": sid2}

    store.close()
    db.close()


class TestSessionQueries:
    def test_get_sessions(self, db_and_store):
        q = db_and_store["queries"]
        result = q.get_sessions()
        assert result["total"] == 2
        assert len(result["sessions"]) == 2

    def test_get_sessions_with_status_filter(self, db_and_store):
        q = db_and_store["queries"]
        result = q.get_sessions(status="completed")
        assert result["total"] == 2

        result = q.get_sessions(status="running")
        assert result["total"] == 0

    def test_get_sessions_pagination(self, db_and_store):
        q = db_and_store["queries"]
        result = q.get_sessions(limit=1, offset=0)
        assert len(result["sessions"]) == 1
        assert result["total"] == 2

    def test_get_session_detail(self, db_and_store):
        q = db_and_store["queries"]
        detail = q.get_session_detail(db_and_store["sid1"])
        assert detail is not None
        assert detail["status"] == "completed"
        assert detail["total_matches"] == 3
        assert len(detail["engine_stats"]) == 1
        assert len(detail["file_type_stats"]) == 2

    def test_get_session_detail_not_found(self, db_and_store):
        q = db_and_store["queries"]
        assert q.get_session_detail("nonexistent") is None

    def test_delete_session(self, db_and_store):
        q = db_and_store["queries"]
        sid = db_and_store["sid1"]
        assert q.delete_session(sid) is True
        assert q.get_session_detail(sid) is None
        # Findings should also be gone
        result = q.get_findings(session_id=sid)
        assert result["total"] == 0

    def test_delete_nonexistent_session(self, db_and_store):
        q = db_and_store["queries"]
        assert q.delete_session("nonexistent") is False


class TestFindingQueries:
    def test_get_all_findings(self, db_and_store):
        q = db_and_store["queries"]
        result = q.get_findings()
        assert result["total"] == 5  # 3 + 2

    def test_get_findings_by_session(self, db_and_store):
        q = db_and_store["queries"]
        result = q.get_findings(session_id=db_and_store["sid1"])
        assert result["total"] == 3

    def test_get_findings_by_type(self, db_and_store):
        q = db_and_store["queries"]
        result = q.get_findings(pii_type="REGEX_EMAIL")
        assert result["total"] == 2

    def test_get_findings_by_severity(self, db_and_store):
        q = db_and_store["queries"]
        result = q.get_findings(severity="HIGH")
        assert result["total"] == 2  # IBAN + NER_PERSON

    def test_get_findings_by_engine(self, db_and_store):
        q = db_and_store["queries"]
        result = q.get_findings(engine="gliner")
        assert result["total"] == 1


class TestAnalyticalQueries:
    def test_pii_type_distribution(self, db_and_store):
        q = db_and_store["queries"]
        dist = q.get_pii_type_distribution()
        assert len(dist) > 0
        types = {d["pii_type"] for d in dist}
        assert "REGEX_EMAIL" in types

    def test_pii_type_distribution_scoped(self, db_and_store):
        q = db_and_store["queries"]
        dist = q.get_pii_type_distribution(session_id=db_and_store["sid1"])
        types = {d["pii_type"] for d in dist}
        assert "NER_PERSON" not in types

    def test_severity_breakdown(self, db_and_store):
        q = db_and_store["queries"]
        breakdown = q.get_severity_breakdown()
        severities = {d["severity"] for d in breakdown}
        assert "HIGH" in severities
        assert "MEDIUM" in severities

    def test_engine_performance(self, db_and_store):
        q = db_and_store["queries"]
        perf = q.get_engine_performance()
        engines = {p["engine"] for p in perf}
        assert "regex" in engines

    def test_file_type_analysis(self, db_and_store):
        q = db_and_store["queries"]
        analysis = q.get_file_type_analysis()
        exts = {a["extension"] for a in analysis}
        assert ".pdf" in exts

    def test_dimension_summary(self, db_and_store):
        q = db_and_store["queries"]
        dims = q.get_dimension_summary()
        dim_names = {d["dimension"] for d in dims}
        assert "contact_information" in dim_names  # REGEX_EMAIL, REGEX_PHONE

    def test_top_affected_files(self, db_and_store):
        q = db_and_store["queries"]
        files = q.get_top_affected_files()
        assert len(files) > 0
        # a.pdf has 2 findings, others have 1
        top_counts = [f["findings_count"] for f in files]
        assert top_counts[0] == 2

    def test_trend_over_time(self, db_and_store):
        q = db_and_store["queries"]
        trend = q.get_trend_over_time(days=1)
        assert isinstance(trend, list)
        # Should have findings for today
        if trend:
            assert trend[0]["total_findings"] > 0

    def test_dashboard_summary(self, db_and_store):
        q = db_and_store["queries"]
        dashboard = q.get_dashboard_summary()
        assert dashboard["total_sessions"] == 2
        assert dashboard["completed_sessions"] == 2
        assert dashboard["total_findings"] == 5
        assert dashboard["unique_files_with_findings"] > 0
        assert len(dashboard["recent_sessions"]) <= 5
        assert len(dashboard["top_pii_types"]) > 0
