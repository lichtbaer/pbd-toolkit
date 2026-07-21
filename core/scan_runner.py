"""Shared scan orchestration service used by both the CLI and the REST API.

``ScanRunner`` owns the scan pipeline: building the match container, statistics,
application context, running the scanner/processor (including concurrency),
post-scan finalisation, analytics completion, output writing, and computing the
exit-code decision.  It deliberately performs **no** presentation: it never calls
``typer.echo`` / ``typer.Exit`` and never prints a console summary.  Callers
(``core/cli.py`` and ``api/scanner_service.py``) supply a fully-built
:class:`~core.config.Config` plus runtime/output options via :class:`ScanRequest`
and receive a :class:`ScanRunResult` they can present or persist as they see fit.

Post-scan *side effects* (redaction, pseudonymisation, webhook) intentionally
stay with the CLI for now; :class:`ScanRunResult` exposes ``matches_by_file`` /
``file_risk_scores`` / ``severity_counts`` so callers can still drive them.  They
are slated for extraction into dedicated handlers under issue #80.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass, field

import typer

from core import constants, scan_reporting
from core.config import Config
from core.context import ApplicationContext
from core.matches import PiiMatch, PiiMatchContainer
from core.processor import TextProcessor
from core.scanner import FileInfo, FileScanner
from core.statistics import Statistics
from core.statistics_aggregator import StatisticsAggregator
from core.writers import OutputWriter

_SEVERITY_LEVELS = ("CRITICAL", "HIGH", "MEDIUM", "LOW")


@dataclass
class ScanRequest:
    """Explicit, typed input to :meth:`ScanRunner.run`.

    The ``config`` is treated as authoritative — callers are expected to have
    already applied flag patching (dedup/chunk/severity/exclude) to it, exactly
    as ``core/cli.py`` does after ``create_config``.
    """

    # Core, already-built objects.
    config: Config
    logger: logging.Logger
    translate_func: Callable[[str], str] = field(default=lambda x: x)

    # Output wiring (caller builds the writer via ``create_output_writer``).
    output_writer: OutputWriter | None = None
    output_format: str = "csv"
    output_file_path: str | None = None
    output_dir: str | None = None
    outslug: str | None = None
    csv_writer: object | None = None
    csv_file_handle: object | None = None

    # PiiMatchContainer construction flags (CLI passes real values; API simplified).
    enable_deduplication: bool = False
    enable_confidence_fusion: bool = False
    validate_structured_findings: bool = True
    min_confidence: float = 0.0

    # Concurrency (issue #79): explicit worker count; API forces 1.
    worker_count: int = 1

    # Incremental cache.
    incremental: bool = False
    cache_path: str | None = None

    # Statistics aggregator.
    statistics_mode: bool = False
    statistics_strict: bool = False
    statistics_output: str | None = None

    # Analytics: caller owns the store + session lifecycle decision.
    analytics_store: object | None = None
    analytics_session_id: str | None = None
    finalize_analytics_session: bool = True

    # CI/CD gate decision data.
    fail_on_severity: str | None = None


@dataclass
class ScanRunResult:
    """Stable output of :meth:`ScanRunner.run`.

    Exposes both summary data and the live ``context`` / ``statistics`` objects
    so callers can reuse ``scan_reporting`` presentation helpers without
    re-plumbing their signatures.
    """

    # Raw scan statistics.
    total_files_found: int
    files_processed: int
    matches_found: int
    total_errors: int
    extension_counts: dict[str, int]
    duration_seconds: float

    # Findings summary.
    file_risk_scores: dict[str, str]
    matches_by_file: dict[str, list[PiiMatch]]
    severity_counts: dict[str, int]

    # Output.
    output_file_path: str | None
    statistics_output_path: str | None

    # Aggregated errors (type -> file list).
    errors: dict[str, list[str]]

    # Exit-code decision data — computed but NOT acted upon by the runner.
    findings_above_threshold: bool
    exit_code: int

    # Live objects for caller-side presentation / persistence.
    context: ApplicationContext
    statistics: Statistics


class ScanRunner:
    """Owns the scan pipeline shared by the CLI and the REST API."""

    @staticmethod
    def _log_analysis_start(
        context: ApplicationContext, output_dir: str | None
    ) -> None:
        """Emit the informational analysis-start log lines.

        This is orchestration-level logging that previously lived inline in
        ``core/cli.py``.  It uses ``logger.info``/``logger.debug`` (never
        ``typer``) so it stays presentation-neutral and shared by all callers.
        """
        logger = context.logger
        logger.info(context._("Analysis"))
        logger.info("====================\n")
        logger.info(
            context._("Analysis started at {}\n").format(context.statistics.start_time)
        )

        if context.config.use_regex:
            logger.info(context._("Regex-based search is active."))
        else:
            logger.info(context._("Regex-based search is *not* active."))

        if context.config.use_ner:
            logger.info(context._("AI-based search is active."))
            if context.config.verbose:
                logger.debug(f"NER Model: {constants.NER_MODEL_NAME}")
                logger.debug(f"NER Threshold: {context.config.ner_threshold}")
                logger.debug(f"NER Labels: {context.config.ner_labels}")
        else:
            logger.info(context._("AI-based search is *not* active."))

        if context.config.verbose:
            logger.debug(f"Search path: {context.config.path}")
            logger.debug(f"Output directory: {output_dir}")
            if context.config.whitelist_path:
                logger.debug(f"Whitelist file: {context.config.whitelist_path}")
                logger.debug(
                    f"Whitelist entries: {len(context.match_container.whitelist)}"
                )

        logger.info("\n")

    def run(self, request: ScanRequest) -> ScanRunResult:
        """Execute a complete scan and return decision data (never raises ``typer.Exit``)."""
        config = request.config
        logger = request.logger

        # --- Match container ---------------------------------------------------
        pmc = PiiMatchContainer(
            enable_deduplication=request.enable_deduplication
            or request.enable_confidence_fusion,
            enable_confidence_fusion=request.enable_confidence_fusion,
            validate_structured_findings=request.validate_structured_findings,
            min_confidence=request.min_confidence,
            min_severity=config.min_severity,
            dedup_max_entries=config.dedup_max_entries,
            max_whitelist_regex_len=config.max_whitelist_regex_len,
        )
        pmc.set_csv_writer(request.csv_writer)
        pmc.set_output_format(request.output_format)
        pmc.set_output_writer(request.output_writer)

        # --- Statistics --------------------------------------------------------
        statistics = Statistics()
        statistics.start()

        statistics_aggregator: StatisticsAggregator | None = None
        if request.statistics_mode:
            statistics_aggregator = StatisticsAggregator(
                strict=request.statistics_strict
            )

        # --- Application context ----------------------------------------------
        context = ApplicationContext(
            config=config,
            logger=logger,
            statistics=statistics,
            match_container=pmc,
            output_writer=request.output_writer,
            translate_func=request.translate_func,
            csv_writer=request.csv_writer,
            csv_file_handle=request.csv_file_handle,
            output_format=request.output_format,
            output_file_path=request.output_file_path,
        )

        if request.analytics_store is not None:
            context.analytics_store = request.analytics_store
            context.analytics_session_id = request.analytics_session_id
            pmc.set_analytics_store(
                request.analytics_store, request.analytics_session_id
            )

        # --- Whitelist ---------------------------------------------------------
        import os

        if config.whitelist_path and os.path.isfile(config.whitelist_path):
            with open(config.whitelist_path, encoding="utf-8") as file:
                pmc.whitelist = file.read().splitlines()
            pmc._compile_whitelist_pattern()

        # --- Analysis header logging (informational, mirrors legacy CLI) ------
        self._log_analysis_start(context, request.output_dir)

        # --- Error tracking ----------------------------------------------------
        errors: dict[str, list[str]] = {}
        _error_lock = threading.Lock()

        def add_error(msg: str, path: str) -> None:
            with _error_lock:
                errors.setdefault(msg, []).append(path)

        # --- Incremental cache -------------------------------------------------
        scan_cache = None
        if request.incremental:
            from core.scan_cache import ScanCache

            _cache_path = request.cache_path or os.path.join(
                request.output_dir or ".", ".pbd_scan_cache.db"
            )
            scan_cache = ScanCache(cache_path=_cache_path, logger=logger)
            _cache_stats = scan_cache.stats()
            logger.info(
                "Incremental scanning enabled. Cache: %s (%s entries)",
                _cache_path,
                _cache_stats["total_entries"],
            )

        # --- Processor + scanner ----------------------------------------------
        text_processor = TextProcessor(config, pmc, statistics=statistics)
        scanner = FileScanner(config)

        worker_count = max(1, int(request.worker_count))
        _stats_lock = threading.Lock()

        def _process_file_impl(file_info: FileInfo) -> None:
            if scan_cache is not None and scan_cache.is_unchanged(file_info.path):
                if config.verbose:
                    logger.debug(
                        "Incremental: skipping unchanged file %s", file_info.path
                    )
                return

            text_processor.process_file(file_info, error_callback=add_error)

            if scan_cache is not None:
                scan_cache.mark_scanned(file_info.path)

            if statistics_aggregator:
                with _stats_lock:
                    statistics_aggregator.add_file_scanned(
                        file_info.path, was_analyzed=True
                    )
                    if config.use_regex:
                        statistics_aggregator.add_file_processed(
                            file_info.path, "regex"
                        )
                    if config.use_ner:
                        statistics_aggregator.add_file_processed(
                            file_info.path, "gliner"
                        )
                    if getattr(config, "use_spacy_ner", False):
                        statistics_aggregator.add_file_processed(
                            file_info.path, "spacy-ner"
                        )
                    if getattr(config, "use_pydantic_ai", False):
                        statistics_aggregator.add_file_processed(
                            file_info.path, "pydantic-ai"
                        )

        executor = None
        if worker_count <= 1:

            def process_file(file_info: FileInfo) -> None:
                _process_file_impl(file_info)
        else:
            import concurrent.futures

            executor = concurrent.futures.ThreadPoolExecutor(max_workers=worker_count)

            def process_file(file_info: FileInfo):
                return executor.submit(_process_file_impl, file_info)

        # --- Scan --------------------------------------------------------------
        try:
            scan_result = scanner.scan(
                path=config.path,
                file_callback=process_file,
                stop_count=config.stop_count,
            )
        finally:
            if executor is not None:
                try:
                    executor.shutdown(wait=True)
                except Exception as exc:
                    logger.warning("Error shutting down scan worker pool: %s", exc)
            if scan_cache is not None:
                scan_cache.close()

        # --- Post-scan finalisation -------------------------------------------
        text_processor.finalize()

        statistics.update_from_scan_result(
            total_files=scan_result.total_files_found,
            files_processed=scan_result.files_processed,
            extension_counts=scan_result.extension_counts,
            errors=scan_result.errors,
        )

        for error_type, file_list in scan_result.errors.items():
            errors.setdefault(error_type, []).extend(file_list)

        statistics.matches_found = len(pmc.pii_matches)

        file_risk_scores, matches_by_file = scan_reporting.compute_file_risk_scores(pmc)

        if statistics_aggregator:
            for match in pmc.pii_matches:
                statistics_aggregator.add_match(match)

        statistics.stop()

        if request.finalize_analytics_session:
            scan_reporting.finalize_analytics(
                request.analytics_store,
                request.analytics_session_id,
                context,
                logger,
            )

        total_errors = sum(len(v) for v in errors.values())
        statistics.total_errors = total_errors

        scan_reporting.log_scan_results(context, errors, scan_result=scan_result)

        # --- Output writing ----------------------------------------------------
        write_error_code = 0
        output_metadata = scan_reporting.build_output_metadata(
            context, errors, file_risk_scores, matches_by_file
        )
        try:
            scan_reporting.write_output(
                context, output_metadata, request.csv_file_handle
            )
        except typer.Exit as exc:
            # ``write_output`` raises ``typer.Exit`` on ``OutputError``.  The runner
            # must not surface CLI control flow — translate it into an exit code.
            write_error_code = getattr(exc, "exit_code", constants.EXIT_GENERAL_ERROR)
            logger.error("Output writing failed (exit code %s)", write_error_code)

        # --- Statistics output -------------------------------------------------
        statistics_output_path: str | None = None
        if statistics_aggregator is not None:
            import argparse

            _stats_args = argparse.Namespace(
                statistics_output=request.statistics_output,
                statistics_strict=request.statistics_strict,
            )
            scan_reporting.write_statistics_output(
                context,
                _stats_args,
                statistics_aggregator,
                request.output_dir or "",
                request.outslug or "",
            )
            statistics_output_path = request.statistics_output or (
                f"{request.output_dir or ''}{request.outslug or ''}_statistics.json"
            )

        # --- Severity counts + CI/CD gate -------------------------------------
        severity_counts = {
            sev: sum(1 for m in pmc.pii_matches if m.severity == sev)
            for sev in _SEVERITY_LEVELS
        }

        findings_above_threshold = False
        if request.fail_on_severity:
            from core.severity import _LEVEL_WEIGHT

            threshold_weight = _LEVEL_WEIGHT.get(request.fail_on_severity.upper(), 2)
            findings_above_threshold = any(
                _LEVEL_WEIGHT.get(m.severity or "", 0) >= threshold_weight
                for m in pmc.pii_matches
            )

        if write_error_code:
            exit_code = write_error_code
        elif findings_above_threshold:
            exit_code = constants.EXIT_FINDINGS_ABOVE_THRESHOLD
        else:
            exit_code = constants.EXIT_SUCCESS

        return ScanRunResult(
            total_files_found=statistics.total_files_found,
            files_processed=statistics.files_processed,
            matches_found=statistics.matches_found,
            total_errors=statistics.total_errors,
            extension_counts=dict(statistics.extension_counts),
            duration_seconds=statistics.duration_seconds,
            file_risk_scores=file_risk_scores,
            matches_by_file=matches_by_file,
            severity_counts=severity_counts,
            output_file_path=request.output_file_path,
            statistics_output_path=statistics_output_path,
            errors=errors,
            findings_above_threshold=findings_above_threshold,
            exit_code=exit_code,
            context=context,
            statistics=statistics,
        )
