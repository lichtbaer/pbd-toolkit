"""Focused tests for the shared :class:`core.scan_runner.ScanRunner`.

These exercise ``ScanRunner.run`` directly — without invoking the Typer CLI or
the HTTP layer — which is the central goal of the shared scan orchestration
service (issue #76). They use only the regex engine so they stay hermetic and
need no optional ML/LLM dependencies.
"""

from __future__ import annotations

import argparse
import concurrent.futures as _real_concurrent_futures
import logging
import sys

from core import constants
from core.config import Config
from core.scan_runner import ScanRequest, ScanRunner


def _make_regex_config(path: str, logger: logging.Logger) -> Config:
    """Build a regex-only :class:`Config` for a given scan path.

    Mirrors the argument namespace the REST API assembles, keeping the test
    independent of CLI argument parsing.
    """
    args = argparse.Namespace(
        path=path,
        regex=True,
        ner=False,
        spacy_ner=False,
        ollama=False,
        openai_compatible=False,
        pydantic_ai=False,
        vector_search=False,
        multimodal=False,
        verbose=False,
        outname=None,
        whitelist=None,
        stop_count=None,
        deduplicate=False,
        incremental=False,
        text_chunk_size=0,
        text_chunk_overlap=200,
        context_chars=0,
        min_confidence=0.0,
        format="json",
        no_header=False,
        use_magic_detection=False,
        magic_fallback=True,
        cache_path=None,
    )
    return Config.from_args(
        args=args,
        logger=logger,
        csv_writer=None,
        csv_file_handle=None,
        translate_func=lambda x: x,
    )


def _run(path: str, **request_kwargs) -> object:
    logger = logging.getLogger("test.scan_runner")
    config = _make_regex_config(path, logger)
    request = ScanRequest(config=config, logger=logger, **request_kwargs)
    return ScanRunner().run(request)


def test_run_regex_scan_finds_pii(tmp_path):
    """A regex scan over a temp directory reports findings and a clean exit."""
    scan_dir = tmp_path / "data"
    scan_dir.mkdir()
    (scan_dir / "sample.txt").write_text(
        "Contact: john.doe@example.com IBAN DE89370400440532013000\n"
    )

    result = _run(str(scan_dir))

    assert result.total_files_found == 1
    assert result.files_processed == 1
    assert result.matches_found >= 1
    # No fail-on-severity gate requested -> success, nothing above threshold.
    assert result.findings_above_threshold is False
    assert result.exit_code == constants.EXIT_SUCCESS
    # Findings summary is populated and consistent with the match count.
    assert sum(result.severity_counts.values()) == result.matches_found
    assert result.matches_by_file


def test_clean_scan_reports_no_findings(tmp_path):
    """A scan over content without PII completes with zero findings."""
    scan_dir = tmp_path / "data"
    scan_dir.mkdir()
    (scan_dir / "notes.txt").write_text("the quick brown fox jumps over\n")

    result = _run(str(scan_dir))

    assert result.files_processed == 1
    assert result.matches_found == 0
    assert result.findings_above_threshold is False
    assert result.exit_code == constants.EXIT_SUCCESS


def test_fail_on_severity_gate_sets_exit_code(tmp_path):
    """When findings meet the threshold the runner flags it via exit-code data."""
    scan_dir = tmp_path / "data"
    scan_dir.mkdir()
    (scan_dir / "sample.txt").write_text(
        "Contact: john.doe@example.com IBAN DE89370400440532013000\n"
    )

    result = _run(str(scan_dir), fail_on_severity="LOW")

    assert result.matches_found >= 1
    assert result.findings_above_threshold is True
    assert result.exit_code == constants.EXIT_FINDINGS_ABOVE_THRESHOLD


def test_run_writes_output_file(tmp_path):
    """With an output writer the runner streams findings to the target file."""
    from core.writers import create_output_writer

    scan_dir = tmp_path / "data"
    scan_dir.mkdir()
    (scan_dir / "sample.txt").write_text("Email: jane.doe@example.com\n")

    out_path = str(tmp_path / "findings.json")
    writer = create_output_writer("json", out_path, include_header=True)

    result = _run(
        str(scan_dir),
        output_writer=writer,
        output_format="json",
        output_file_path=out_path,
    )

    assert result.output_file_path == out_path
    import os

    assert os.path.isfile(out_path)
    assert os.path.getsize(out_path) > 0


def test_runner_does_not_raise_typer_exit(tmp_path):
    """The runner must never surface CLI control flow (``typer.Exit``)."""
    import typer

    scan_dir = tmp_path / "data"
    scan_dir.mkdir()
    (scan_dir / "sample.txt").write_text("Email: jane.doe@example.com\n")

    try:
        _run(str(scan_dir))
    except typer.Exit:  # pragma: no cover - defensive
        raise AssertionError("ScanRunner.run leaked a typer.Exit")


# --- Concurrency ownership (issue #79) --------------------------------------
#
# ``ScanRunner`` is the sole owner of the file-worker thread pool: it decides
# whether to build a ``ThreadPoolExecutor`` from ``worker_count`` and is
# responsible for shutting it down. ``FileScanner`` never constructs one
# itself. These tests pin that ownership boundary directly, using a spy
# subclass so the pool is still real (no behavior faked) but instantiation and
# shutdown are observable.
#
# ``concurrent.futures.ThreadPoolExecutor`` is also used, unrelated to file-
# level concurrency, for per-chunk regex timeout protection (see
# ``core/engines/regex_engine.py`` and ``core/matches.py``) — every regex scan
# creates one of *those* per text chunk. The spy below must stay a fully
# functional drop-in replacement (including the context-manager protocol) so
# it doesn't break that unrelated usage, and it only records instances
# constructed from ``core/scan_runner.py`` itself so the two concerns aren't
# conflated.

_RealThreadPoolExecutor = _real_concurrent_futures.ThreadPoolExecutor


class _SpyThreadPoolExecutor:
    """Wraps the real ``ThreadPoolExecutor``; records only scan_runner-owned instances."""

    instances: list[_SpyThreadPoolExecutor] = []

    def __init__(self, *args, **kwargs):
        self.max_workers = kwargs.get("max_workers") or (args[0] if args else None)
        # Bind the *original* class captured before patching — looking it up
        # via ``concurrent.futures.ThreadPoolExecutor`` here would resolve to
        # this very spy again (infinite recursion) since the module attribute
        # stays patched for the duration of the test.
        self._real = _RealThreadPoolExecutor(*args, **kwargs)
        self.shutdown_called = False
        caller_file = sys._getframe(1).f_code.co_filename
        if caller_file.endswith("scan_runner.py"):
            _SpyThreadPoolExecutor.instances.append(self)

    def submit(self, *args, **kwargs):
        return self._real.submit(*args, **kwargs)

    def shutdown(self, *args, **kwargs):
        self.shutdown_called = True
        self._real.shutdown(*args, **kwargs)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown(wait=True)
        return False


def _install_spy_executor(monkeypatch) -> type[_SpyThreadPoolExecutor]:
    _SpyThreadPoolExecutor.instances = []
    monkeypatch.setattr(
        _real_concurrent_futures, "ThreadPoolExecutor", _SpyThreadPoolExecutor
    )
    return _SpyThreadPoolExecutor


def test_safe_mode_never_constructs_a_thread_pool(tmp_path, monkeypatch):
    """``worker_count=1`` (``--mode safe``) must stay fully sequential."""
    spy = _install_spy_executor(monkeypatch)

    scan_dir = tmp_path / "data"
    scan_dir.mkdir()
    (scan_dir / "sample.txt").write_text("Email: jane.doe@example.com\n")

    result = _run(str(scan_dir), worker_count=1)

    assert result.files_processed == 1
    assert spy.instances == []


def test_parallel_mode_uses_a_single_owned_thread_pool(tmp_path, monkeypatch):
    """``worker_count>1`` must route every file through one ``ScanRunner``-owned pool."""
    spy = _install_spy_executor(monkeypatch)

    scan_dir = tmp_path / "data"
    scan_dir.mkdir()
    for i in range(5):
        (scan_dir / f"sample{i}.txt").write_text(f"Email: person{i}@example.com\n")

    result = _run(str(scan_dir), worker_count=3)

    assert result.files_processed == 5
    assert len(spy.instances) == 1
    assert spy.instances[0].max_workers == 3
    assert spy.instances[0].shutdown_called is True


def test_executor_is_shut_down_even_when_the_scan_raises(tmp_path, monkeypatch):
    """Executor cleanup must run deterministically, even on a scanner failure."""
    spy = _install_spy_executor(monkeypatch)

    scan_dir = tmp_path / "data"
    scan_dir.mkdir()
    (scan_dir / "sample.txt").write_text("Email: jane.doe@example.com\n")

    from core.scanner import FileScanner

    def _boom(self, *args, **kwargs):
        raise RuntimeError("simulated scan failure")

    monkeypatch.setattr(FileScanner, "scan", _boom)

    try:
        _run(str(scan_dir), worker_count=2)
        raise AssertionError("expected RuntimeError to propagate")
    except RuntimeError as exc:
        assert "simulated scan failure" in str(exc)

    assert len(spy.instances) == 1
    assert spy.instances[0].shutdown_called is True


def test_worker_thread_exception_is_captured_not_fatal(tmp_path, monkeypatch):
    """One file's processing exception must not abort the whole parallel run."""
    _install_spy_executor(monkeypatch)

    scan_dir = tmp_path / "data"
    scan_dir.mkdir()
    (scan_dir / "bad.txt").write_text("Email: jane.doe@example.com\n")
    (scan_dir / "good.txt").write_text("Email: john.doe@example.com\n")

    from core.processor import TextProcessor

    original_process_file = TextProcessor.process_file

    def _flaky_process_file(self, file_info, error_callback=None):
        if file_info.path.endswith("bad.txt"):
            raise RuntimeError("simulated per-file failure")
        return original_process_file(self, file_info, error_callback=error_callback)

    monkeypatch.setattr(TextProcessor, "process_file", _flaky_process_file)

    result = _run(str(scan_dir), worker_count=2)

    # The run itself completes and still reports the good file's finding.
    assert result.files_processed == 2
    assert result.matches_found >= 1
    assert result.total_errors >= 1
    assert any("simulated per-file failure" in msg for msg in result.errors)
