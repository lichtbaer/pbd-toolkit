"""Focused tests for the shared :class:`core.scan_runner.ScanRunner`.

These exercise ``ScanRunner.run`` directly — without invoking the Typer CLI or
the HTTP layer — which is the central goal of the shared scan orchestration
service (issue #76). They use only the regex engine so they stay hermetic and
need no optional ML/LLM dependencies.
"""

from __future__ import annotations

import argparse
import logging

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
