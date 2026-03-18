"""Background scan service that wraps the existing scanning pipeline.

Scans are run in a ``ThreadPoolExecutor`` so the API can accept new
requests while scans are in progress.
"""

from __future__ import annotations

import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from analytics.store import AnalyticsStore

logger = logging.getLogger(__name__)


class ScannerService:
    """Manages background scan jobs using the existing scan pipeline."""

    def __init__(self, analytics_store: AnalyticsStore, max_workers: int = 2) -> None:
        self._store = analytics_store
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="scan")
        self._active: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start_scan(
        self,
        path: str,
        engines: list[str] | None = None,
        profile: str | None = None,
        deduplicate: bool = False,
        incremental: bool = False,
        text_chunk_size: int = 0,
        min_confidence: float = 0.0,
        context_chars: int = 0,
    ) -> str:
        """Submit a scan job and return the session ID immediately."""
        config_summary = {
            "engines": engines or ["regex"],
            "profile": profile,
            "deduplicate": deduplicate,
            "incremental": incremental,
        }
        session_id = self._store.create_session(
            scan_path=path,
            config_summary=config_summary,
            source="api",
        )

        with self._lock:
            self._active[session_id] = {"status": "running"}

        self._executor.submit(
            self._run_scan,
            session_id=session_id,
            path=path,
            engines=engines or ["regex"],
            profile=profile,
            deduplicate=deduplicate,
            incremental=incremental,
            text_chunk_size=text_chunk_size,
            min_confidence=min_confidence,
            context_chars=context_chars,
        )

        return session_id

    def get_active_scans(self) -> dict[str, dict[str, Any]]:
        """Return a snapshot of currently active scans."""
        with self._lock:
            return dict(self._active)

    def shutdown(self) -> None:
        """Wait for running scans to finish."""
        self._executor.shutdown(wait=True)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run_scan(
        self,
        session_id: str,
        path: str,
        engines: list[str],
        profile: str | None,
        deduplicate: bool,
        incremental: bool,
        text_chunk_size: int,
        min_confidence: float,
        context_chars: int,
    ) -> None:
        """Execute the scan pipeline in a worker thread."""
        try:
            # Validate path
            if not os.path.isdir(path):
                self._store.fail_session(session_id, f"Path is not a directory: {path}")
                return

            # Build CLI-compatible args namespace
            import argparse

            args = argparse.Namespace(
                path=path,
                regex="regex" in engines,
                ner="gliner" in engines,
                spacy_ner="spacy" in engines,
                ollama="ollama" in engines,
                openai_compatible="openai" in engines,
                pydantic_ai="pydantic-ai" in engines,
                vector_search="vector" in engines,
                multimodal=False,
                verbose=False,
                outname=None,
                whitelist=None,
                stop_count=None,
                deduplicate=deduplicate,
                incremental=incremental,
                text_chunk_size=text_chunk_size,
                text_chunk_overlap=200,
                context_chars=context_chars,
                min_confidence=min_confidence,
                format="json",
                no_header=False,
                use_magic_detection=False,
                magic_fallback=True,
                # Defaults for engine-specific settings
                spacy_model="de_core_news_lg",
                ollama_url="http://localhost:11434",
                ollama_model="llama3.2",
                openai_api_base="https://api.openai.com/v1",
                openai_api_key=os.environ.get("OPENAI_API_KEY"),
                openai_model="gpt-3.5-turbo",
                pydantic_ai_provider="openai",
                pydantic_ai_model=None,
                pydantic_ai_api_key=None,
                pydantic_ai_base_url=None,
                vector_model="sentence-transformers/all-MiniLM-L6-v2",
                vector_threshold=0.75,
                vector_save_index=None,
                vector_load_index=None,
                vector_custom_exemplars=None,
                cache_path=None,
            )

            scan_logger = logging.getLogger(f"scan.{session_id[:8]}")

            from config import Config
            from core.statistics import Statistics
            from matches import PiiMatchContainer

            # Create config (this also loads regex patterns, NER models, etc.)
            config_obj = Config.from_args(
                args=args,
                logger=scan_logger,
                csv_writer=None,
                csv_file_handle=None,
                translate_func=lambda x: x,
            )
            config_obj.enable_deduplication = deduplicate
            config_obj.text_chunk_size = text_chunk_size
            config_obj.context_chars = context_chars
            config_obj.min_confidence = min_confidence

            statistics = Statistics()
            statistics.start()

            pmc = PiiMatchContainer(
                enable_deduplication=deduplicate,
                min_confidence=min_confidence,
            )
            pmc.set_analytics_store(self._store, session_id)

            # Run the scanner
            from core.scanner import FileScanner

            scanner = FileScanner(config=config_obj, logger=scan_logger)
            scan_result = scanner.scan()

            statistics.update_from_scan_result(
                total_files=scan_result.total_files,
                files_processed=scan_result.files_processed,
                extension_counts=scan_result.extension_counts,
                errors=scan_result.errors,
            )

            # Process files with the text processor
            from core.processor import TextProcessor

            processor = TextProcessor(config=config_obj, logger=scan_logger)
            for file_path in scan_result.processed_files:
                try:
                    processor.process_file(
                        file_path=file_path,
                        match_container=pmc,
                        statistics=statistics,
                    )
                except Exception as exc:
                    scan_logger.debug("Error processing %s: %s", file_path, exc)

            statistics.stop()

            # Complete session
            self._store.complete_session(
                session_id=session_id,
                total_files=statistics.total_files_found,
                files_processed=statistics.files_processed,
                total_matches=statistics.matches_found,
                total_errors=statistics.total_errors,
                duration_sec=statistics.duration_seconds,
            )

            # Record per-engine stats
            for engine_name, match_count in statistics.matches_by_engine.items():
                self._store.record_engine_stats(
                    session_id=session_id,
                    engine=engine_name,
                    matches_found=match_count,
                )

            # Record per-file-type stats
            for ext, ext_count in statistics.extension_counts.items():
                self._store.record_file_type_stats(
                    session_id=session_id,
                    extension=ext,
                    files_scanned=ext_count,
                )

        except Exception as exc:
            logger.error("Scan %s failed: %s", session_id[:8], exc, exc_info=True)
            try:
                self._store.fail_session(session_id, str(exc))
            except Exception:
                pass
        finally:
            with self._lock:
                self._active.pop(session_id, None)
