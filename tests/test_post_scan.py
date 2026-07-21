"""Tests for `core.post_scan`: post-scan integration handlers (issue #80).

These call handlers directly -- without invoking the Typer CLI -- which is the
point of extracting them: post-scan behavior must be testable on its own.
"""

from __future__ import annotations

import logging

import pytest

from core.matches import PiiMatch
from core.post_scan import (
    PostScanContext,
    PseudonymizationHandler,
    RedactionHandler,
    WebhookHandler,
    run_post_scan_handlers,
)


@pytest.fixture
def logger() -> logging.Logger:
    return logging.getLogger("test.post_scan")


def _context(
    tmp_path,
    logger: logging.Logger,
    matches_by_file: dict[str, list[PiiMatch]] | None = None,
) -> PostScanContext:
    return PostScanContext(
        matches_by_file=matches_by_file or {},
        scan_path=str(tmp_path),
        output_dir=str(tmp_path),
        output_file_path=str(tmp_path / "results.csv"),
        files_processed=3,
        duration_seconds=1.5,
        severity_counts={"CRITICAL": 1, "HIGH": 2, "MEDIUM": 0, "LOW": 0},
        logger=logger,
    )


def _sample_file_with_match(tmp_path):
    src = tmp_path / "sample.txt"
    src.write_text("Contact: jane@example.com")
    match = PiiMatch(
        text="jane@example.com",
        file=str(src),
        type="EMAIL",
        engine="regex",
        char_offset=src.read_text().index("jane@example.com"),
    )
    return src, {str(src): [match]}


class TestRedactionHandler:
    def test_writes_redacted_copy_and_reports_target_dir(self, tmp_path, logger):
        _src, matches_by_file = _sample_file_with_match(tmp_path)
        handler = RedactionHandler()
        context = _context(tmp_path, logger, matches_by_file)

        outcome = handler.handle(context)

        assert outcome is not None
        assert outcome.handler == "redaction"
        assert outcome.ok is True
        assert outcome.target == str(tmp_path / "redacted")
        assert len(outcome.output_paths) == 1

    def test_honors_explicit_output_dir(self, tmp_path, logger):
        _src, matches_by_file = _sample_file_with_match(tmp_path)
        custom_dir = str(tmp_path / "custom_redacted")
        handler = RedactionHandler(output_dir=custom_dir)

        outcome = handler.handle(_context(tmp_path, logger, matches_by_file))

        assert outcome.target == custom_dir

    def test_returns_none_when_no_matches(self, tmp_path, logger):
        handler = RedactionHandler()
        outcome = handler.handle(_context(tmp_path, logger, {}))
        assert outcome is None


class TestPseudonymizationHandler:
    def test_writes_pseudonymized_copy_and_reports_target_dir(self, tmp_path, logger):
        _src, matches_by_file = _sample_file_with_match(tmp_path)
        handler = PseudonymizationHandler()
        context = _context(tmp_path, logger, matches_by_file)

        outcome = handler.handle(context)

        assert outcome is not None
        assert outcome.handler == "pseudonymization"
        assert outcome.ok is True
        assert outcome.target == str(tmp_path / "pseudonymized")
        assert len(outcome.output_paths) == 1

    def test_returns_none_when_no_matches(self, tmp_path, logger):
        handler = PseudonymizationHandler()
        outcome = handler.handle(_context(tmp_path, logger, {}))
        assert outcome is None


class TestWebhookHandler:
    def test_delivers_payload_via_injected_sender(self, tmp_path, logger):
        captured = {}

        def fake_sender(url, payload, timeout):
            captured["url"] = url
            captured["payload"] = payload
            captured["timeout"] = timeout
            return 200

        _src, matches_by_file = _sample_file_with_match(tmp_path)
        handler = WebhookHandler(url="https://example.test/hook", sender=fake_sender)

        outcome = handler.handle(_context(tmp_path, logger, matches_by_file))

        assert outcome.ok is True
        assert outcome.handler == "webhook"
        assert outcome.http_status == 200
        assert outcome.target == "https://example.test/hook"
        assert captured["url"] == "https://example.test/hook"
        assert captured["payload"]["total_findings"] == 1
        assert captured["payload"]["files_scanned"] == 3
        assert captured["payload"]["severity_counts"] == {
            "CRITICAL": 1,
            "HIGH": 2,
            "MEDIUM": 0,
            "LOW": 0,
        }

    def test_failure_is_reported_not_raised(self, tmp_path, logger):
        def failing_sender(url, payload, timeout):
            raise TimeoutError("endpoint unreachable")

        handler = WebhookHandler(url="https://example.test/hook", sender=failing_sender)

        outcome = handler.handle(_context(tmp_path, logger))

        assert outcome.ok is False
        assert outcome.handler == "webhook"
        assert "endpoint unreachable" in outcome.error

    def test_runs_even_with_no_findings(self, tmp_path, logger):
        """Unlike redaction/pseudonymization, the webhook always fires."""

        def fake_sender(url, payload, timeout):
            return 204

        handler = WebhookHandler(url="https://example.test/hook", sender=fake_sender)
        outcome = handler.handle(_context(tmp_path, logger))

        assert outcome is not None
        assert outcome.ok is True


class TestRunPostScanHandlers:
    def test_runs_all_handlers_and_collects_outcomes(self, tmp_path, logger):
        _src, matches_by_file = _sample_file_with_match(tmp_path)
        handlers = [
            RedactionHandler(),
            WebhookHandler(url="https://example.test/hook", sender=lambda *a: 200),
        ]

        outcomes = run_post_scan_handlers(
            handlers, _context(tmp_path, logger, matches_by_file)
        )

        assert [o.handler for o in outcomes] == ["redaction", "webhook"]
        assert all(o.ok for o in outcomes)

    def test_omits_handlers_that_return_none(self, tmp_path, logger):
        handlers = [RedactionHandler(), PseudonymizationHandler()]
        outcomes = run_post_scan_handlers(handlers, _context(tmp_path, logger, {}))
        assert outcomes == []

    def test_one_handler_failing_does_not_block_the_others(self, tmp_path, logger):
        class ExplodingHandler:
            name = "boom"

            def handle(self, context):
                raise RuntimeError("integration is down")

        _src, matches_by_file = _sample_file_with_match(tmp_path)
        handlers = [
            ExplodingHandler(),
            WebhookHandler(url="https://example.test/hook", sender=lambda *a: 200),
        ]

        outcomes = run_post_scan_handlers(
            handlers, _context(tmp_path, logger, matches_by_file)
        )

        assert len(outcomes) == 2
        boom, webhook = outcomes
        assert boom.handler == "boom"
        assert boom.ok is False
        assert "integration is down" in boom.error
        assert webhook.ok is True

    def test_handler_returning_failed_outcome_does_not_raise(self, tmp_path, logger):
        def failing_sender(url, payload, timeout):
            raise ConnectionError("refused")

        handlers = [
            WebhookHandler(url="https://example.test/hook", sender=failing_sender)
        ]
        outcomes = run_post_scan_handlers(handlers, _context(tmp_path, logger))

        assert len(outcomes) == 1
        assert outcomes[0].ok is False
