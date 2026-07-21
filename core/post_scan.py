"""Post-scan integration handlers: redaction, pseudonymization, webhook notification.

Extracted from the CLI's inline post-scan side effects (issue #80) so they run
through one explicit, testable interface instead of ad-hoc blocks in
``core/cli.py``. Handlers receive a :class:`PostScanContext` snapshot of the
finished scan and return a :class:`PostScanOutcome` (or ``None`` if there was
nothing to do). Handlers never raise for expected failure modes (e.g. an
unreachable webhook endpoint) -- the outcome carries ``ok``/``error`` for the
caller to present. Handlers intentionally return structured data rather than
translated strings: presentation (``typer.echo``, message translation) and
exit-code decisions stay in the CLI layer, per the ticket's own scoping.

The REST API does not wire these in yet (it has no redact/pseudonymize/webhook
request fields today) but can reuse :func:`run_post_scan_handlers` directly
once it does.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from core.matches import PiiMatch

# (url, json-serializable payload, timeout seconds) -> HTTP status code.
# Raises on transport/HTTP failure. Injectable so tests never hit the network.
WebhookSender = Callable[[str, dict[str, object], float], int]


@dataclass
class PostScanContext:
    """Everything a post-scan handler needs, decoupled from ``Config``/``ApplicationContext``."""

    matches_by_file: dict[str, list[PiiMatch]]
    scan_path: str
    output_dir: str
    output_file_path: str | None
    files_processed: int
    duration_seconds: float
    severity_counts: dict[str, int]
    logger: logging.Logger


@dataclass
class PostScanOutcome:
    """Structured result of running one handler, for the caller to present."""

    handler: str
    ok: bool
    # Output directory (redaction/pseudonymization) or webhook URL notified.
    target: str | None = None
    output_paths: dict[str, str] = field(default_factory=dict)
    http_status: int | None = None
    error: str | None = None


class PostScanHandler(Protocol):
    """A handler that reacts to a completed scan."""

    name: str

    def handle(self, context: PostScanContext) -> PostScanOutcome | None:
        """Run the handler; return ``None`` if it had nothing to do."""
        ...


@dataclass
class RedactionHandler:
    """Writes redacted copies of scanned files (PII replaced by placeholders)."""

    output_dir: str | None = None
    name: str = "redaction"

    def handle(self, context: PostScanContext) -> PostScanOutcome | None:
        if not context.matches_by_file:
            return None
        from core.redactor import redact_files

        target_dir = self.output_dir or os.path.join(context.output_dir, "redacted")
        paths = redact_files(
            matches_by_file=context.matches_by_file,
            output_dir=target_dir,
            logger=context.logger,
        )
        if not paths:
            return None
        return PostScanOutcome(
            handler=self.name, ok=True, target=target_dir, output_paths=paths
        )


@dataclass
class PseudonymizationHandler:
    """Writes pseudo-anonymized copies of scanned files (realistic fake values)."""

    output_dir: str | None = None
    name: str = "pseudonymization"

    def handle(self, context: PostScanContext) -> PostScanOutcome | None:
        if not context.matches_by_file:
            return None
        from core.pseudonymizer import pseudonymize_files

        target_dir = self.output_dir or os.path.join(
            context.output_dir, "pseudonymized"
        )
        paths = pseudonymize_files(
            matches_by_file=context.matches_by_file,
            output_dir=target_dir,
            logger=context.logger,
        )
        if not paths:
            return None
        return PostScanOutcome(
            handler=self.name, ok=True, target=target_dir, output_paths=paths
        )


def _default_webhook_sender(
    url: str, payload: dict[str, object], timeout: float
) -> int:
    """Default HTTP POST implementation (stdlib only, no new dependency)."""
    import urllib.request

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310  # nosec B310
        return resp.status


@dataclass
class WebhookHandler:
    """POSTs a scan summary to a configured URL.

    ``sender`` is the injectable HTTP abstraction called for delivery -- tests
    substitute a fake to avoid real network calls and to exercise timeout/
    failure handling deterministically.
    """

    url: str
    timeout: float = 10.0
    sender: WebhookSender = _default_webhook_sender
    name: str = "webhook"

    def handle(self, context: PostScanContext) -> PostScanOutcome | None:
        total_findings = sum(len(v) for v in context.matches_by_file.values())
        payload: dict[str, object] = {
            "scan_path": context.scan_path,
            "total_findings": total_findings,
            "files_scanned": context.files_processed,
            "duration_sec": context.duration_seconds,
            "severity_counts": dict(context.severity_counts),
            "output_file": context.output_file_path,
        }
        try:
            status = self.sender(self.url, payload, self.timeout)
        except Exception as exc:
            return PostScanOutcome(
                handler=self.name, ok=False, target=self.url, error=str(exc)
            )
        return PostScanOutcome(
            handler=self.name, ok=True, target=self.url, http_status=status
        )


def run_post_scan_handlers(
    handlers: list[PostScanHandler], context: PostScanContext
) -> list[PostScanOutcome]:
    """Run each configured handler in order, isolating failures.

    A handler raising unexpectedly (rather than returning a failed outcome)
    is caught and logged here too -- one integration failing (e.g. a webhook
    endpoint timing out) must never corrupt the scan result or prevent the
    remaining handlers from running.
    """
    outcomes: list[PostScanOutcome] = []
    for handler in handlers:
        try:
            outcome = handler.handle(context)
        except Exception as exc:
            context.logger.warning(
                "Post-scan handler '%s' failed: %s", handler.name, exc
            )
            outcomes.append(
                PostScanOutcome(handler=handler.name, ok=False, error=str(exc))
            )
            continue
        if outcome is not None:
            outcomes.append(outcome)
    return outcomes
