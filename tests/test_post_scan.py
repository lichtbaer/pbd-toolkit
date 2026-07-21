"""Tests for post-scan integration handlers (core.post_scan, issue #80).

These exercise redaction/pseudonymization/webhook delivery entirely through
``core.post_scan`` handler objects — no Typer ``CliRunner`` involved — to pin
the ticket's "post-scan behavior can be tested without invoking the CLI"
acceptance criterion.
"""

import logging

from core.matches import PiiMatch
from core.post_scan import (
    PseudonymizationHandler,
    RedactionHandler,
    WebhookDeliveryResult,
    WebhookHandler,
    build_pseudonymization_handler,
    build_redaction_handler,
)
from core.scan_runner import ScanRunResult


def _match(text, type_="REGEX_EMAIL", offset=None):
    return PiiMatch(text=text, file="doc.txt", type=type_, char_offset=offset)


def _make_result(**overrides) -> ScanRunResult:
    defaults = dict(
        total_files_found=1,
        files_processed=1,
        matches_found=1,
        total_errors=0,
        extension_counts={".txt": 1},
        duration_seconds=0.5,
        file_risk_scores={},
        matches_by_file={},
        severity_counts={"CRITICAL": 0, "HIGH": 1, "MEDIUM": 0, "LOW": 0},
        output_file_path="out.csv",
        statistics_output_path=None,
        errors={},
        findings_above_threshold=False,
        exit_code=0,
        context=None,
        statistics=None,
    )
    defaults.update(overrides)
    return ScanRunResult(**defaults)


class FakeResponse:
    def __init__(self, status_code=200, raise_exc=None):
        self.status_code = status_code
        self._raise_exc = raise_exc

    def raise_for_status(self):
        if self._raise_exc:
            raise self._raise_exc


class TestRedactionHandler:
    def test_no_matches_by_file_is_a_noop(self, tmp_path):
        handler = RedactionHandler(output_dir=str(tmp_path / "redacted"))
        result = _make_result(matches_by_file={})

        assert handler.handle(result) == {}
        assert not (tmp_path / "redacted").exists()

    def test_writes_redacted_copy_when_matches_present(self, tmp_path):
        src = tmp_path / "doc.txt"
        src.write_text("Contact me at test@example.com today")
        out_dir = tmp_path / "redacted"

        handler = RedactionHandler(output_dir=str(out_dir))
        result = _make_result(
            matches_by_file={str(src): [_match("test@example.com", offset=14)]}
        )

        redacted_paths = handler.handle(result)

        assert str(src) in redacted_paths
        redacted_text = open(redacted_paths[str(src)]).read()
        assert "[REDACTED:REGEX_EMAIL]" in redacted_text
        assert "test@example.com" not in redacted_text

    def test_accepts_explicit_logger(self, tmp_path):
        src = tmp_path / "doc.txt"
        src.write_text("test@example.com")
        handler = RedactionHandler(output_dir=str(tmp_path / "redacted"))
        result = _make_result(
            matches_by_file={str(src): [_match("test@example.com", offset=0)]}
        )

        # Must not raise when handed a real logger instance.
        handler.handle(result, logger=logging.getLogger("test.redaction"))


class TestPseudonymizationHandler:
    def test_no_matches_by_file_is_a_noop(self, tmp_path):
        handler = PseudonymizationHandler(output_dir=str(tmp_path / "pseudo"))
        result = _make_result(matches_by_file={})

        assert handler.handle(result) == {}
        assert not (tmp_path / "pseudo").exists()

    def test_writes_pseudonymized_copy_when_matches_present(self, tmp_path):
        src = tmp_path / "doc.txt"
        src.write_text("Contact me at test@example.com today")
        out_dir = tmp_path / "pseudo"

        handler = PseudonymizationHandler(output_dir=str(out_dir))
        result = _make_result(
            matches_by_file={str(src): [_match("test@example.com", offset=14)]}
        )

        pseudo_paths = handler.handle(result)

        assert str(src) in pseudo_paths
        pseudo_text = open(pseudo_paths[str(src)]).read()
        assert "test@example.com" not in pseudo_text


class TestBuildHandlerHelpers:
    def test_build_redaction_handler_defaults_to_base_dir_subfolder(self):
        handler = build_redaction_handler(None, "/scan/output")
        assert handler.output_dir == "/scan/output/redacted"

    def test_build_redaction_handler_respects_explicit_dir(self):
        handler = build_redaction_handler("/custom/dir", "/scan/output")
        assert handler.output_dir == "/custom/dir"

    def test_build_pseudonymization_handler_defaults_to_base_dir_subfolder(self):
        handler = build_pseudonymization_handler(None, "/scan/output")
        assert handler.output_dir == "/scan/output/pseudonymized"

    def test_build_pseudonymization_handler_respects_explicit_dir(self):
        handler = build_pseudonymization_handler("/custom/dir", "/scan/output")
        assert handler.output_dir == "/custom/dir"


class TestWebhookHandler:
    def test_successful_delivery_posts_expected_payload(self):
        captured = {}

        def fake_post(url, json=None, timeout=None, headers=None):
            captured["url"] = url
            captured["json"] = json
            captured["timeout"] = timeout
            captured["headers"] = headers
            return FakeResponse(status_code=200)

        handler = WebhookHandler(
            url="https://example.com/hook",
            scan_path="/scan/target",
            http_post=fake_post,
        )
        result = _make_result(
            matches_found=3,
            files_processed=10,
            duration_seconds=1.25,
            severity_counts={"CRITICAL": 1, "HIGH": 2, "MEDIUM": 0, "LOW": 0},
            output_file_path="out.csv",
        )

        outcome = handler.handle(result)

        assert outcome == WebhookDeliveryResult(delivered=True, status_code=200)
        assert captured["url"] == "https://example.com/hook"
        assert captured["headers"] == {"Content-Type": "application/json"}
        assert captured["json"] == {
            "scan_path": "/scan/target",
            "total_findings": 3,
            "files_scanned": 10,
            "duration_sec": 1.25,
            "severity_counts": {"CRITICAL": 1, "HIGH": 2, "MEDIUM": 0, "LOW": 0},
            "output_file": "out.csv",
        }

    def test_delivery_failure_does_not_raise_and_is_logged(self, caplog):
        def failing_post(url, json=None, timeout=None, headers=None):
            raise ConnectionError("connection refused")

        handler = WebhookHandler(
            url="https://example.com/hook",
            scan_path="/scan/target",
            http_post=failing_post,
        )
        result = _make_result()

        # Explicit logger name: some other test suite (CLI --quiet tests) may
        # have raised the shared "core" logger's level process-wide, which
        # would otherwise mask this child logger's WARNING via inherited
        # effective level.
        with caplog.at_level(logging.WARNING, logger="core.post_scan"):
            outcome = handler.handle(result)

        assert outcome.delivered is False
        assert "connection refused" in outcome.error
        assert any("Webhook delivery" in rec.getMessage() for rec in caplog.records)

    def test_http_error_status_counts_as_failure(self):
        def fake_post(url, json=None, timeout=None, headers=None):
            return FakeResponse(status_code=500, raise_exc=Exception("HTTP 500"))

        handler = WebhookHandler(
            url="https://example.com/hook",
            scan_path="/scan/target",
            http_post=fake_post,
        )

        outcome = handler.handle(_make_result())

        assert outcome.delivered is False
        assert "HTTP 500" in outcome.error

    def test_default_http_post_is_requests_post(self):
        import requests

        handler = WebhookHandler(url="https://example.com/hook", scan_path="/x")
        assert handler.http_post is requests.post

    def test_timeout_defaults_to_ten_seconds(self):
        handler = WebhookHandler(url="https://example.com/hook", scan_path="/x")
        assert handler.timeout == 10.0
