"""Tests for the REST API endpoints.

These tests require the ``api`` extra (fastapi, uvicorn, pydantic).
They are skipped automatically if the dependencies are not installed.
"""

import pytest

try:
    from fastapi.testclient import TestClient
    from api.app import create_app

    HAS_API_DEPS = True
except ImportError:
    HAS_API_DEPS = False

pytestmark = pytest.mark.skipif(not HAS_API_DEPS, reason="API dependencies not installed")


@pytest.fixture
def client(tmp_path):
    """Provide a FastAPI TestClient with a temporary analytics DB."""
    db_path = str(tmp_path / "test_api.db")
    app = create_app(analytics_db_path=db_path)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def seeded_client(tmp_path):
    """Provide a TestClient with pre-seeded analytics data."""
    from analytics.store import AnalyticsStore

    db_path = str(tmp_path / "test_api_seeded.db")
    store = AnalyticsStore(db_path=db_path)

    sid = store.create_session(scan_path="/data", config_summary={"engines": ["regex"]})
    store.record_finding(sid, "/data/a.pdf", "REGEX_EMAIL", "regex", "MEDIUM", 0.9)
    store.record_finding(sid, "/data/b.docx", "REGEX_IBAN", "regex", "HIGH", 0.95)
    store.record_engine_stats(sid, "regex", matches_found=2, files_processed=5)
    store.record_file_type_stats(sid, ".pdf", files_scanned=3, matches_found=1)
    store.complete_session(sid, total_files=5, files_processed=5, total_matches=2, duration_sec=1.5)
    store.close()

    app = create_app(analytics_db_path=db_path)
    with TestClient(app) as c:
        yield {"client": c, "session_id": sid}


class TestHealthEndpoint:
    def test_health(self, client):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"


class TestSystemEndpoints:
    def test_engines(self, client):
        resp = client.get("/api/v1/system/engines")
        assert resp.status_code == 200
        engines = resp.json()
        assert isinstance(engines, list)
        names = {e["name"] for e in engines}
        assert "regex" in names

    def test_profiles(self, client):
        resp = client.get("/api/v1/system/profiles")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestScanEndpoints:
    def test_list_scans_empty(self, client):
        resp = client.get("/api/v1/scans")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["sessions"] == []

    def test_list_scans_with_data(self, seeded_client):
        resp = seeded_client["client"].get("/api/v1/scans")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1

    def test_get_scan_detail(self, seeded_client):
        sid = seeded_client["session_id"]
        resp = seeded_client["client"].get(f"/api/v1/scans/{sid}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == sid
        assert data["status"] == "completed"
        assert data["total_matches"] == 2

    def test_get_scan_not_found(self, client):
        resp = client.get("/api/v1/scans/00000000000000000000000000000000")
        assert resp.status_code == 404

    def test_get_scan_findings(self, seeded_client):
        sid = seeded_client["session_id"]
        resp = seeded_client["client"].get(f"/api/v1/scans/{sid}/findings")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2

    def test_get_scan_findings_with_filter(self, seeded_client):
        sid = seeded_client["session_id"]
        resp = seeded_client["client"].get(f"/api/v1/scans/{sid}/findings?severity=HIGH")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1

    def test_delete_scan(self, seeded_client):
        sid = seeded_client["session_id"]
        resp = seeded_client["client"].delete(f"/api/v1/scans/{sid}")
        assert resp.status_code == 204
        # Verify it's gone
        resp = seeded_client["client"].get(f"/api/v1/scans/{sid}")
        assert resp.status_code == 404

    def test_delete_scan_not_found(self, client):
        resp = client.delete("/api/v1/scans/00000000000000000000000000000000")
        assert resp.status_code == 404


class TestAnalyticsEndpoints:
    def test_dashboard(self, seeded_client):
        resp = seeded_client["client"].get("/api/v1/analytics/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_sessions"] == 1
        assert data["total_findings"] == 2

    def test_trends(self, seeded_client):
        resp = seeded_client["client"].get("/api/v1/analytics/trends")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_types(self, seeded_client):
        resp = seeded_client["client"].get("/api/v1/analytics/types")
        assert resp.status_code == 200
        types = resp.json()
        assert len(types) == 2  # REGEX_EMAIL and REGEX_IBAN

    def test_severity(self, seeded_client):
        resp = seeded_client["client"].get("/api/v1/analytics/severity")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_engines_analytics(self, seeded_client):
        resp = seeded_client["client"].get("/api/v1/analytics/engines")
        assert resp.status_code == 200

    def test_file_types(self, seeded_client):
        resp = seeded_client["client"].get("/api/v1/analytics/file-types")
        assert resp.status_code == 200

    def test_dimensions(self, seeded_client):
        resp = seeded_client["client"].get("/api/v1/analytics/dimensions")
        assert resp.status_code == 200
        dims = resp.json()
        dim_names = {d["dimension"] for d in dims}
        assert "contact_information" in dim_names  # REGEX_EMAIL

    def test_top_files(self, seeded_client):
        resp = seeded_client["client"].get("/api/v1/analytics/top-files")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


# ---------------------------------------------------------------------------
# Security tests
# ---------------------------------------------------------------------------


class TestPathTraversal:
    """Verify that scan paths outside allowed roots are rejected."""

    def test_path_outside_root_is_rejected(self, tmp_path):
        db_path = str(tmp_path / "pt.db")
        allowed = str(tmp_path / "safe")
        (tmp_path / "safe").mkdir()
        app = create_app(analytics_db_path=db_path, allowed_scan_roots=[allowed])
        with TestClient(app) as c:
            resp = c.post("/api/v1/scans", json={"path": "/etc"})
            assert resp.status_code == 400
            assert "outside" in resp.json()["detail"].lower() or "not a directory" in resp.json()["detail"].lower()

    def test_dotdot_traversal_is_rejected(self, tmp_path):
        db_path = str(tmp_path / "pt2.db")
        safe = tmp_path / "safe"
        safe.mkdir()
        app = create_app(analytics_db_path=db_path, allowed_scan_roots=[str(safe)])
        with TestClient(app) as c:
            resp = c.post("/api/v1/scans", json={"path": str(safe / ".." / "..")})
            assert resp.status_code == 400

    def test_allowed_path_is_accepted(self, tmp_path):
        """A path inside allowed roots should not get a 400."""
        db_path = str(tmp_path / "pt3.db")
        safe = tmp_path / "safe"
        safe.mkdir()
        app = create_app(analytics_db_path=db_path, allowed_scan_roots=[str(safe)])
        with TestClient(app) as c:
            resp = c.post("/api/v1/scans", json={"path": str(safe)})
            # 202 means the scan was accepted (it may fail later, but path validation passed)
            assert resp.status_code == 202


class TestAPIKeyAuth:
    """Verify Bearer token authentication middleware."""

    @pytest.fixture
    def auth_client(self, tmp_path):
        db_path = str(tmp_path / "auth.db")
        app = create_app(analytics_db_path=db_path, api_key="test-secret-key")
        with TestClient(app) as c:
            yield c

    def test_missing_key_returns_401(self, auth_client):
        resp = auth_client.get("/api/v1/scans")
        assert resp.status_code == 401

    def test_wrong_key_returns_403(self, auth_client):
        resp = auth_client.get("/api/v1/scans", headers={"Authorization": "Bearer wrong-key"})
        assert resp.status_code == 403

    def test_correct_key_succeeds(self, auth_client):
        resp = auth_client.get(
            "/api/v1/scans", headers={"Authorization": "Bearer test-secret-key"}
        )
        assert resp.status_code == 200

    def test_health_without_auth(self, auth_client):
        resp = auth_client.get("/api/v1/health")
        assert resp.status_code == 200


class TestCORS:
    """Verify CORS configuration uses safe defaults."""

    def test_default_origins_not_wildcard(self, tmp_path):
        db_path = str(tmp_path / "cors.db")
        app = create_app(analytics_db_path=db_path)
        # Check that CORS middleware is configured with non-wildcard origins
        from starlette.middleware.cors import CORSMiddleware as _CM

        for mw in app.user_middleware:
            if mw.cls is _CM:
                assert "*" not in mw.kwargs.get("allow_origins", [])
                break

    def test_wildcard_disables_credentials(self, tmp_path):
        db_path = str(tmp_path / "cors2.db")
        app = create_app(analytics_db_path=db_path, cors_origins=["*"])
        from starlette.middleware.cors import CORSMiddleware as _CM

        for mw in app.user_middleware:
            if mw.cls is _CM:
                assert mw.kwargs.get("allow_credentials") is False
                break


class TestGroupByValidation:
    """Verify that invalid group_by values are rejected."""

    def test_invalid_group_by_returns_422(self, seeded_client):
        resp = seeded_client["client"].get("/api/v1/analytics/trends?group_by=invalid")
        assert resp.status_code == 422

    def test_valid_group_by_accepted(self, seeded_client):
        for val in ("day", "week", "month"):
            resp = seeded_client["client"].get(f"/api/v1/analytics/trends?group_by={val}")
            assert resp.status_code == 200


class TestSessionIdValidation:
    """Verify that malformed session IDs are rejected."""

    def test_invalid_session_id_returns_400(self, client):
        resp = client.get("/api/v1/scans/not-a-valid-hex-id")
        assert resp.status_code == 400

    def test_sql_injection_session_id_returns_400(self, client):
        resp = client.get("/api/v1/scans/1' OR '1'='1")
        assert resp.status_code == 400

    def test_invalid_session_id_on_findings(self, client):
        resp = client.get("/api/v1/scans/not-a-hex-id/findings")
        assert resp.status_code == 400

    def test_invalid_analytics_session_id(self, client):
        resp = client.get("/api/v1/analytics/types?session_id=invalid")
        assert resp.status_code == 400


class TestRateLimiting:
    """Verify rate limiting middleware."""

    def test_scan_rate_limit(self, tmp_path):
        db_path = str(tmp_path / "rl.db")
        safe = tmp_path / "scandir"
        safe.mkdir()
        app = create_app(
            analytics_db_path=db_path,
            allowed_scan_roots=[str(safe)],
            scan_rate_limit=2,
        )
        with TestClient(app) as c:
            # First two requests should succeed (202)
            for _ in range(2):
                resp = c.post("/api/v1/scans", json={"path": str(safe)})
                assert resp.status_code == 202
            # Third should be rate limited
            resp = c.post("/api/v1/scans", json={"path": str(safe)})
            assert resp.status_code == 429
            assert "Retry-After" in resp.headers
