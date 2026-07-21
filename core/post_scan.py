"""Post-scan integration handlers extracted from CLI orchestration (issue #80).

``core/scan_runner.py`` deliberately performs no presentation or side effects
beyond writing the primary scan output and finalizing analytics; everything
else that happens *after* a scan completes — redacted/pseudonymized copies of
scanned files, webhook notification of the scan summary — is optional,
integration-shaped behavior that used to be inlined directly in the Typer CLI
command (``core/cli.py``). That made it impossible to unit test without
invoking the CLI, and impossible for the REST API (or any future caller
holding a :class:`~core.scan_runner.ScanRunResult`) to reuse.

Each handler here wraps one such side effect behind a small, independently
constructible class with a uniform ``handle(result, logger=None)`` entry
point. Handlers never raise on failure — they log through the supplied
logger (module logger as a fallback) and return a result object the caller
can use for presentation; this keeps webhook/redaction/pseudonymization
failures from corrupting or aborting an otherwise-successful scan.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

import requests

if TYPE_CHECKING:
    from core.scan_runner import ScanRunResult

_logger = logging.getLogger(__name__)


@runtime_checkable
class PostScanHandler(Protocol):
    """Structural protocol every post-scan handler satisfies.

    Mirrors the ``Protocol``-based style already used for injectable
    dependencies (see ``core/protocols.py`` and ``core/engines/base.py``)
    rather than an ABC, so handlers stay trivially fakeable in tests.
    """

    def handle(
        self, result: ScanRunResult, logger: logging.Logger | None = None
    ) -> Any: ...


@dataclass
class RedactionHandler:
    """Writes redacted copies of scanned files that contain PII matches."""

    output_dir: str

    def handle(
        self, result: ScanRunResult, logger: logging.Logger | None = None
    ) -> dict[str, str]:
        if not result.matches_by_file:
            return {}

        from core.redactor import redact_files

        return redact_files(
            matches_by_file=result.matches_by_file,
            output_dir=self.output_dir,
            logger=logger or _logger,
        )


@dataclass
class PseudonymizationHandler:
    """Writes pseudo-anonymized copies of scanned files that contain PII matches."""

    output_dir: str

    def handle(
        self, result: ScanRunResult, logger: logging.Logger | None = None
    ) -> dict[str, str]:
        if not result.matches_by_file:
            return {}

        from core.pseudonymizer import pseudonymize_files

        return pseudonymize_files(
            matches_by_file=result.matches_by_file,
            output_dir=self.output_dir,
            logger=logger or _logger,
        )


@dataclass
class WebhookDeliveryResult:
    """Outcome of a :class:`WebhookHandler` delivery attempt."""

    delivered: bool
    status_code: int | None = None
    error: str | None = None


@dataclass
class WebhookHandler:
    """POSTs a JSON scan summary to a configured URL.

    ``http_post`` defaults to :func:`requests.post` but is injectable so
    tests can supply a fake without monkeypatching the ``requests`` module
    or touching the network (see the ticket's "testable HTTP abstraction"
    acceptance criterion).
    """

    url: str
    scan_path: str
    timeout: float = 10.0
    http_post: Callable[..., Any] = field(default=requests.post)

    def handle(
        self, result: ScanRunResult, logger: logging.Logger | None = None
    ) -> WebhookDeliveryResult:
        log = logger or _logger
        payload = self._build_payload(result)
        try:
            response = self.http_post(
                self.url,
                json=payload,
                timeout=self.timeout,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            return WebhookDeliveryResult(
                delivered=True, status_code=response.status_code
            )
        except Exception as exc:
            log.warning("Webhook delivery to %s failed: %s", self.url, exc)
            return WebhookDeliveryResult(delivered=False, error=str(exc))

    def _build_payload(self, result: ScanRunResult) -> dict[str, Any]:
        return {
            "scan_path": self.scan_path,
            "total_findings": result.matches_found,
            "files_scanned": result.files_processed,
            "duration_sec": result.duration_seconds,
            "severity_counts": dict(result.severity_counts),
            "output_file": result.output_file_path,
        }


def build_redaction_handler(
    output_dir: str | None, base_output_dir: str
) -> RedactionHandler:
    """Resolve the redaction output directory the same way the CLI always has."""
    return RedactionHandler(
        output_dir=output_dir or os.path.join(base_output_dir, "redacted")
    )


def build_pseudonymization_handler(
    output_dir: str | None, base_output_dir: str
) -> PseudonymizationHandler:
    """Resolve the pseudonymization output directory the same way the CLI always has."""
    return PseudonymizationHandler(
        output_dir=output_dir or os.path.join(base_output_dir, "pseudonymized")
    )
