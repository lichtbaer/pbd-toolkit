"""Regression tests for the REST API scan pipeline.

These exercise ``ScannerService._run_scan`` end-to-end against the current core
scanner API. They guard against the drift fixed in #75, where the API used to
call ``FileScanner(config=..., logger=...)``, ``scanner.scan()`` without a path,
and read non-existent ``ScanResult`` fields (``total_files``/``processed_files``).

The scan uses only the regex engine, which is always available, so the test is
hermetic and needs no optional ML/LLM dependencies.
"""

from __future__ import annotations

from analytics.queries import AnalyticsQueries
from analytics.store import AnalyticsStore
from api.scanner_service import ScannerService
from core.scanner import ScanResult
from core.statistics import Statistics


def test_run_scan_pipeline_completes(tmp_path):
    """A regex scan over a temp directory completes and records results."""
    scan_dir = tmp_path / "data"
    scan_dir.mkdir()
    (scan_dir / "sample.txt").write_text(
        "Contact: john.doe@example.com IBAN DE89370400440532013000\n"
    )

    store = AnalyticsStore(db_path=str(tmp_path / "analytics.db"))
    service = ScannerService(store, allowed_scan_roots=[str(scan_dir)])
    try:
        session_id = service.start_scan(str(scan_dir), engines=["regex"])
        # shutdown() waits for the worker thread, making the scan deterministic.
        service.shutdown()
        # Query while the store connection is still open.
        session = AnalyticsQueries(store._db).get_session_detail(session_id)
    finally:
        store.close()

    assert session is not None
    assert session["status"] == "completed"
    assert session["total_files"] == 1
    assert session["files_processed"] == 1
    # The sample contains at least an email and an IBAN, both regex-detectable.
    assert session["total_matches"] >= 1


def test_scanner_service_uses_stable_registry_snapshots(tmp_path):
    """ScannerService captures registry snapshots once at construction and
    reuses them for every scan (issue #78), rather than reading whatever the
    global ``FileProcessorRegistry``/``EngineRegistry`` look like at scan time.
    """
    from core.engines.registry import IsolatedEngineRegistry
    from file_processors.registry import IsolatedFileProcessorRegistry

    store = AnalyticsStore(db_path=str(tmp_path / "analytics.db"))
    try:
        service = ScannerService(store, allowed_scan_roots=[str(tmp_path)])
        assert isinstance(
            service._file_processor_registry, IsolatedFileProcessorRegistry
        )
        assert isinstance(service._engine_registry, IsolatedEngineRegistry)
        assert "regex" in service._engine_registry.list_engines()
        assert len(service._file_processor_registry.get_all_processors()) > 0
    finally:
        store.close()


def test_run_scan_invalid_path_marks_session_failed(tmp_path):
    """A scan whose path is not a directory ends in a failed session."""
    store = AnalyticsStore(db_path=str(tmp_path / "analytics.db"))
    missing = tmp_path / "does-not-exist"
    # Allow the parent root so the path passes start_scan's allowed-root check
    # but fails the directory check inside _run_scan.
    service = ScannerService(store, allowed_scan_roots=[str(tmp_path)])
    try:
        session_id = store.create_session(scan_path=str(missing), source="api")
        service._run_scan(
            session_id=session_id,
            path=str(missing),
            engines=["regex"],
            profile=None,
            deduplicate=False,
            incremental=False,
            text_chunk_size=0,
            min_confidence=0.0,
            context_chars=0,
        )
        service.shutdown()
        session = AnalyticsQueries(store._db).get_session_detail(session_id)
    finally:
        store.close()

    assert session is not None
    assert session["status"] == "failed"


def test_statistics_maps_scan_result_fields():
    """Field-mapping guard: Statistics consumes the real ScanResult fields.

    Locks in the correct attribute names (``total_files_found`` /
    ``files_processed``) so the API mapping cannot silently drift again.
    """
    result = ScanResult(
        total_files_found=7,
        files_processed=5,
        extension_counts={".txt": 5},
        errors={},
    )
    stats = Statistics()
    stats.update_from_scan_result(
        total_files=result.total_files_found,
        files_processed=result.files_processed,
        extension_counts=result.extension_counts,
        errors=result.errors,
    )

    assert stats.total_files_found == 7
    assert stats.files_processed == 5
    assert stats.extension_counts == {".txt": 5}
