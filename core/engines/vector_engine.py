"""Vector-based PII detection engine using semantic similarity.

Detection strategy
------------------
For each incoming text chunk the engine:

1. Embeds the chunk with a sentence-transformers model (local, no network).
2. Computes cosine similarity against a set of pre-embedded PII *exemplar*
   texts (one set per category, defined in ``core/indexer/pii_queries.py``).
3. Returns a ``DetectionResult`` for every PII category whose best exemplar
   similarity exceeds the configured threshold.

The engine optionally also stores all processed chunks in a FAISS index so
that cross-document queries can be run after the scan completes.

Triage mode
-----------
When ``config.use_vector_triage`` is True the engine acts as a pre-filter:
``TextProcessor`` calls ``triage_pass(text)`` before running any other engine
and skips the chunk entirely if the vector engine finds no PII signal.

Usage
-----
Standalone::

    pii-toolkit scan /data --vector-search

As triage pre-filter (saves LLM API calls)::

    pii-toolkit scan /data --vector-search --vector-triage --pydantic-ai ...
"""

from __future__ import annotations

import threading
from typing import Optional

from core.config import Config
from core.engines.base import DetectionResult
from core.indexer.document_indexer import DocumentIndexer


class VectorEngine:
    """Semantic-similarity PII detection engine.

    Attributes:
        name: Engine identifier used in ``EngineRegistry`` and output.
        thread_safe: True – the underlying model is shared via class-level
            cache and protected by an internal lock.
        enabled: Set from ``config.use_vector_search``.
    """

    name = "vector-search"
    thread_safe = True

    def __init__(self, config: Config) -> None:
        self.config = config
        self.enabled: bool = bool(getattr(config, "use_vector_search", False))
        self.triage_mode: bool = bool(getattr(config, "use_vector_triage", False))

        threshold: float = float(getattr(config, "vector_threshold", 0.75))
        model_name: str = str(
            getattr(config, "vector_model", "sentence-transformers/all-MiniLM-L6-v2")
        )
        save_index: Optional[str] = getattr(config, "vector_save_index", None) or None
        load_index: Optional[str] = getattr(config, "vector_load_index", None) or None
        custom_exemplars: Optional[str] = (
            getattr(config, "vector_custom_exemplars", None) or None
        )

        self._indexer = DocumentIndexer(
            model_name=model_name,
            threshold=threshold,
            save_index_path=save_index,
            load_index_path=load_index,
            custom_exemplars_path=custom_exemplars,
            verbose=bool(getattr(config, "verbose", False)),
        )

        self._chunk_counter: int = 0
        self._counter_lock = threading.Lock()
        # Thread-local storage for current file context (path + hash)
        self._thread_local = threading.local()
        self._available: Optional[bool] = None

    # ------------------------------------------------------------------
    # DetectionEngine protocol
    # ------------------------------------------------------------------

    def detect(
        self,
        text: str,
        labels: list[str] | None = None,
    ) -> list[DetectionResult]:
        """Detect PII categories in *text* via exemplar similarity.

        Each returned ``DetectionResult`` covers the entire *text* chunk;
        ``entity_type`` is one of the ``VECTOR_*`` category names, and
        ``confidence`` is the cosine similarity score (0.0 – 1.0).

        Args:
            text: Text chunk to analyse.
            labels: Ignored (categories are determined by the exemplar index).

        Returns:
            List of DetectionResult objects, one per matching category.
        """
        if not self.enabled or not text.strip():
            return []

        try:
            matches = self._indexer.detect(text)
        except Exception as exc:
            self.config.logger.warning(f"[vector] Detection failed: {exc}")
            if self.config.verbose:
                self.config.logger.debug("[vector] Error detail:", exc_info=True)
            return []

        if not matches:
            return []

        # Optionally store this chunk in the full-document index
        if getattr(self.config, "vector_save_index", None):
            with self._counter_lock:
                idx = self._chunk_counter
                self._chunk_counter += 1
            try:
                file_path = getattr(self._thread_local, "file_path", None) or "<scan>"
                file_hash = getattr(self._thread_local, "file_hash", "") or ""
                # add_chunk is non-blocking and thread-safe
                self._indexer.add_chunk(
                    text, file_path=file_path, chunk_idx=idx, file_hash=file_hash
                )
            except Exception as exc:
                if self.config.verbose:
                    self.config.logger.debug(
                        "[vector] Chunk indexing failed: %s", exc, exc_info=True
                    )

        results = []
        for match in matches:
            results.append(
                DetectionResult(
                    text=text,
                    entity_type=match.category,
                    confidence=round(match.score, 4),
                    engine_name=self.name,
                    metadata={
                        "similarity": round(match.score, 4),
                        "best_exemplar": match.best_exemplar,
                        "model": self._indexer.model_name,
                        "threshold": self._indexer.threshold,
                    },
                )
            )
        return results

    def is_available(self) -> bool:
        """Return True when the engine is enabled and sentence-transformers is installed."""
        if not self.enabled:
            return False
        if self._available is None:
            self._available = self._indexer.is_available()
            if not self._available and self.config.verbose:
                self.config.logger.warning(
                    "[vector] sentence-transformers is not installed. "
                    "Install with: pip install sentence-transformers\n"
                    "  or: pip install 'pii-toolkit[vector]'"
                )
        return self._available

    # ------------------------------------------------------------------
    # File context (called by TextProcessor before each file)
    # ------------------------------------------------------------------

    def set_current_file(self, file_path: str, file_hash: str = "") -> None:
        """Set the file context for subsequent ``detect()`` calls in this thread.

        Called by ``TextProcessor`` before processing each file so that
        ``add_chunk`` records the correct source file path and SHA-256 hash
        in the document index.  This enables proper cross-document analysis
        and incremental-scan checks after the fact.

        Args:
            file_path: Absolute path of the file being processed.
            file_hash: SHA-256 hex digest of the file; empty if not computed.
        """
        self._thread_local.file_path = file_path
        self._thread_local.file_hash = file_hash

    # ------------------------------------------------------------------
    # Triage helper (called by TextProcessor when use_vector_triage=True)
    # ------------------------------------------------------------------

    def triage_pass(self, text: str) -> bool:
        """Return True if *text* contains any PII signal above the threshold.

        Used as a cheap pre-filter: only chunks that pass are forwarded to
        more expensive engines (LLMs, GLiNER, etc.).

        Args:
            text: Text chunk to test.

        Returns:
            True  → PII signal detected, proceed with full engine pipeline.
            False → No signal, skip this chunk for other engines.
        """
        if not text.strip():
            return False
        try:
            matches = self._indexer.detect(text)
            return len(matches) > 0
        except Exception:
            # On error, be conservative and let other engines run
            return True

    # ------------------------------------------------------------------
    # Post-scan finalisation
    # ------------------------------------------------------------------

    def finalize(self) -> None:
        """Persist the FAISS index if a save path was configured.

        Call this after all files have been processed.
        """
        if getattr(self.config, "vector_save_index", None):
            try:
                self._indexer.save_index()
            except Exception as exc:
                self.config.logger.warning(f"[vector] Failed to save index: {exc}")
