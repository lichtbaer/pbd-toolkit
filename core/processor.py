"""Text and file processing for PII detection."""

from contextlib import nullcontext
import threading
import time
import re
from typing import Callable, Optional

import docx.opc.exceptions

from core.config import Config
from core.scanner import FileInfo
from core.statistics import Statistics
from core.engines import EngineRegistry
from core.engines.base import DetectionEngine
from file_processors import FileProcessorRegistry
from file_processors.image_processor import ImageProcessor
from core.matches import PiiMatchContainer


_ASCII_CONTROL_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")
# Remove ASCII control chars (except \n, \t, \r). This is what typically breaks NLP.
_ASCII_CONTROL_TRANSLATION = {
    i: None
    for i in list(range(0x00, 0x09)) + [0x0B, 0x0C] + list(range(0x0E, 0x20)) + [0x7F]
}


class TextProcessor:
    """Processes text content for PII detection using multiple engines.

    This class handles:
    - Multiple detection engines (regex, GLiNER, spaCy, LLMs, etc.)
    - Statistics tracking
    - Error handling
    - Thread-safe operations
    """

    def __init__(
        self,
        config: Config,
        match_container: PiiMatchContainer,
        statistics: Optional[Statistics] = None,
    ):
        """Initialize text processor.

        Args:
            config: Configuration object with detection settings
            match_container: Container for storing detected PII matches
            statistics: Optional statistics tracker (uses config.ner_stats if None)
        """
        self.config = config
        self.match_container = match_container
        self.statistics = statistics

        # Thread locks for thread-safe operations
        self._process_lock = threading.Lock()
        # Backward-compatibility: some tests expect a dedicated NER lock
        self._ner_lock = threading.Lock()

        # Initialize engines from registry (may be refreshed if config changes)
        self.engines: list[DetectionEngine] = []
        self._engine_locks: dict[str, threading.Lock] = {}
        self._enabled_engine_names: list[str] = []
        self._init_engines()

    def _init_engines(self) -> None:
        """(Re)initialize engines and per-engine locks from current config."""
        self.engines = []
        enabled_engines = self._get_enabled_engines()
        self._enabled_engine_names = enabled_engines

        for engine_name in enabled_engines:
            engine = EngineRegistry.get_engine(engine_name, self.config)
            if engine and engine.is_available():
                self.engines.append(engine)
                if getattr(self.config, "verbose", False):
                    getattr(self.config, "logger", None) and self.config.logger.debug(
                        f"Engine '{engine_name}' loaded and enabled"
                    )

        # Locks only for engines that are not thread-safe. Thread-safe engines
        # (e.g., regex) should run concurrently across file workers.
        self._engine_locks = {
            engine.name: threading.Lock()
            for engine in self.engines
            if not getattr(engine, "thread_safe", False)
        }

    def _ensure_engines_current(self) -> None:
        """Refresh engines if config flags have changed since initialization.

        This helps tests and supports scenarios where a Config is mutated after
        processor construction.
        """
        enabled_engines = self._get_enabled_engines()
        if enabled_engines != self._enabled_engine_names:
            self._init_engines()

    def _get_enabled_engines(self) -> list[str]:
        """Get list of enabled engine names from config.

        Returns:
            List of engine names to use
        """
        engines = []
        if self.config.use_regex:
            engines.append("regex")
        if self.config.use_ner:
            engines.append("gliner")
        if getattr(self.config, "use_spacy_ner", False):
            engines.append("spacy-ner")
        if getattr(self.config, "use_vector_search", False):
            engines.append("vector-search")
        # Use PydanticAI unified engine if explicitly enabled or if any legacy LLM engine is enabled
        # PydanticAI engine automatically handles ollama, openai-compatible, and multimodal
        if (
            getattr(self.config, "use_pydantic_ai", False)
            or getattr(self.config, "use_ollama", False)
            or getattr(self.config, "use_openai_compatible", False)
            or getattr(self.config, "use_multimodal", False)
        ):
            engines.append("pydantic-ai")
        return engines

    @staticmethod
    def _update_ner_stats(stats, processing_time: float, results: list) -> None:
        """Update NER statistics for a single stats object."""
        stats.total_chunks_processed += 1
        stats.total_processing_time += processing_time
        stats.total_entities_found += len(results)
        for result in results:
            entity_type = result.entity_type
            stats.entities_by_type[entity_type] = (
                stats.entities_by_type.get(entity_type, 0) + 1
            )

    def _handle_engine_error(
        self, engine_name: str, file_path: str, error: Exception, level: str = "warning"
    ) -> None:
        """Record an engine processing error in stats and logs."""
        if engine_name == "gliner":
            with self._process_lock:
                self.config.ner_stats.errors += 1
                if self.statistics:
                    self.statistics.ner_stats.errors += 1
        msg = f"Engine '{engine_name}' error for {file_path}: {type(error).__name__}: {error}"
        log_fn = getattr(self.config.logger, level, self.config.logger.warning)
        log_fn(msg, exc_info=self.config.verbose)
        self._add_error(f"{engine_name} error: {type(error).__name__}", file_path)

    @staticmethod
    def _split_into_chunks(text: str, chunk_size: int, overlap: int) -> list[str]:
        """Split *text* into overlapping segments of at most *chunk_size* characters.

        Adjacent chunks share *overlap* characters so that entities near a
        boundary are not cut off. If the text is shorter than *chunk_size*,
        it is returned as-is in a single-element list.

        Args:
            text: The text to chunk.
            chunk_size: Maximum number of characters per chunk (must be > 0).
            overlap: Number of characters shared between adjacent chunks.

        Returns:
            List of text segments.
        """
        if chunk_size <= 0 or len(text) <= chunk_size:
            return [text]

        overlap = max(0, min(overlap, chunk_size - 1))
        step = chunk_size - overlap
        chunks = []
        start = 0
        while start < len(text):
            chunks.append(text[start : start + chunk_size])
            start += step
        return chunks

    def process_text(self, text: str, file_path: str, *, _deadline: float | None = None) -> None:
        """Process text content with all enabled detection engines.

        Args:
            text: Text content to analyze
            file_path: Path to the file containing the text
            _deadline: Optional monotonic deadline (internal, set by process_file)
        """
        if not text.strip():
            return

        # Ensure engines reflect current config flags
        self._ensure_engines_current()

        # Vector triage pre-filter: skip chunk if no PII signal detected
        if getattr(self.config, "use_vector_triage", False):
            if not self._vector_triage_pass(text):
                return

        # Clean text to remove ASCII control characters that confuse NLP models (especially spaCy).
        # Fast path: if none are present, avoid O(n) Python-level filtering.
        if _ASCII_CONTROL_RE.search(text):
            text = text.translate(_ASCII_CONTROL_TRANSLATION)

        if not text.strip():
            return

        if self.config.verbose:
            # Log a snippet of the text to debug extraction quality
            snippet = text[:100].replace("\n", "\\n")
            self.config.logger.debug(
                f"Processing text from {file_path} (len={len(text)}): '{snippet}...'"
            )

        all_results = []

        # Determine text chunks for processing.  Chunking applies when
        # text_chunk_size > 0 AND the text exceeds that size.
        chunk_size = getattr(self.config, "text_chunk_size", 0)
        chunk_overlap = getattr(self.config, "text_chunk_overlap", 200)
        text_chunks = self._split_into_chunks(text, chunk_size, chunk_overlap)

        # Run all enabled engines
        for engine in self.engines:
            # Check per-file deadline before starting the next engine
            if _deadline is not None and time.monotonic() > _deadline:
                self.config.logger.warning(
                    f"Per-file timeout reached for {file_path}, skipping remaining engines"
                )
                break

            start_time = time.time()
            try:
                results = []
                for chunk in text_chunks:
                    chunk_results = self._run_engine_detect(
                        engine, chunk, labels=self.config.ner_labels
                    )
                    results.extend(chunk_results)

                processing_time = time.time() - start_time
                all_results.extend(results)

                # Update statistics for all AI/NER engines
                if engine.name in [
                    "gliner",
                    "spacy-ner",
                    "ollama",
                    "openai-compatible",
                    "multimodal",
                    "pydantic-ai",
                ]:
                    with self._process_lock:
                        self._update_ner_stats(
                            self.config.ner_stats, processing_time, results
                        )
                        if self.statistics:
                            self._update_ner_stats(
                                self.statistics.ner_stats, processing_time, results
                            )

            except RuntimeError as e:
                self._handle_engine_error(engine.name, file_path, e, "warning")
            except MemoryError as e:
                self._handle_engine_error(engine.name, file_path, e, "error")
            except Exception as e:
                self._handle_engine_error(engine.name, file_path, e, "error")

        # Add all results to match container and update per-engine statistics
        if all_results:
            _ctx_chars = getattr(self.config, "context_chars", 0)
            with self._process_lock:
                self.match_container.add_detection_results(
                    all_results,
                    file_path,
                    source_text=text if _ctx_chars > 0 else None,
                    context_chars=_ctx_chars,
                )
                if self.statistics:
                    for result in all_results:
                        self.statistics.add_match(engine=result.engine_name)

    def _run_engine_detect(
        self,
        engine: DetectionEngine,
        text: str,
        labels: list[str] | None = None,
        image_path: str | None = None,
    ):
        """Run a single engine detect call with appropriate synchronization.

        Thread safety is handled by:
        - per-engine locks in this processor for engines marked thread_safe=False
        - engine-internal locks (if implemented by the engine)

        This helper is used for both text and image detection to avoid bypassing
        synchronization in the image path.
        """
        engine_lock = self._engine_locks.get(engine.name)
        lock_ctx = engine_lock if engine_lock is not None else nullcontext()
        with lock_ctx:
            if image_path is not None:
                # PydanticAIEngine supports image_path kwarg; other engines ignore it
                return engine.detect(text, labels, image_path=image_path)  # type: ignore[arg-type]
            return engine.detect(text, labels)

    def process_file(
        self,
        file_info: FileInfo,
        error_callback: Optional[Callable[[str, str], None]] = None,
    ) -> bool:
        """Process a single file: extract text and detect PII.

        Args:
            file_info: FileInfo object with file path and metadata
            error_callback: Optional callback function for error reporting.
                          Receives (error_message, file_path)

        Returns:
            True if file was processed successfully, False otherwise
        """
        # Ensure engines reflect current config flags
        self._ensure_engines_current()

        full_path = file_info.path
        ext = file_info.extension
        mime_type = getattr(file_info, "mime_type", None) or ""

        # Notify the vector engine of the current file so that indexed chunks
        # carry the correct file path and hash (enables cross-document analysis
        # and incremental-scan support).
        if getattr(self.config, "vector_save_index", None):
            for engine in self.engines:
                if engine.name == "vector-search" and hasattr(
                    engine, "set_current_file"
                ):
                    _file_hash = ""
                    try:
                        import hashlib as _hashlib

                        _h = _hashlib.sha256()
                        with open(full_path, "rb") as _fh:
                            for _block in iter(lambda: _fh.read(65536), b""):
                                _h.update(_block)
                        _file_hash = _h.hexdigest()
                    except OSError:
                        pass
                    engine.set_current_file(full_path, _file_hash)
                    break

        # Get appropriate processor for this file type
        processor = FileProcessorRegistry.get_processor(ext, full_path, mime_type)

        if processor is None:
            if self.config.verbose:
                self.config.logger.debug(f"Skipping unsupported file type: {full_path}")
            return False

        file_start_time = time.monotonic()
        file_timeout = getattr(self.config, "max_processing_time_seconds", 300)

        try:
            # Handle image files with PydanticAI engine (supports multimodal)
            if isinstance(processor, ImageProcessor):
                if (
                    self.config.use_multimodal
                    or getattr(self.config, "use_pydantic_ai", False)
                    or getattr(self.config, "use_ollama", False)
                    or getattr(self.config, "use_openai_compatible", False)
                ):
                    # Get PydanticAI engine (handles multimodal detection)
                    pydantic_ai_engine = None
                    for engine in self.engines:
                        if engine.name == "pydantic-ai":
                            pydantic_ai_engine = engine
                            break

                    if pydantic_ai_engine:
                        # Process image with PydanticAI engine
                        results = self._run_engine_detect(
                            pydantic_ai_engine,
                            "",
                            labels=self.config.ner_labels,
                            image_path=full_path,
                        )
                        if results:
                            with self._process_lock:
                                self.match_container.add_detection_results(
                                    results, full_path
                                )
                        if self.config.verbose:
                            self.config.logger.debug(
                                f"Processed image with PydanticAI engine: {full_path}"
                            )
                    else:
                        if self.config.verbose:
                            self.config.logger.debug(
                                f"PydanticAI engine not available, skipping image: {full_path}"
                            )
                else:
                    if self.config.verbose:
                        self.config.logger.debug(
                            f"Multimodal detection not enabled, skipping image: {full_path}"
                        )
                return True

            # Calculate deadline for this file
            deadline = file_start_time + file_timeout if file_timeout > 0 else None

            # Extract text: some processors yield chunks (PDF, SQLite, MBOX, ZIP),
            # others return a single string.
            result = processor.extract_text(full_path)
            if isinstance(result, str):
                if result.strip():
                    self.process_text(result, full_path, _deadline=deadline)
            else:
                # Iterator-based processor (PDF, SQLite, MBOX, ZIP)
                for text_chunk in result:
                    if deadline and time.monotonic() > deadline:
                        self.config.logger.warning(
                            f"Per-file timeout ({file_timeout}s) reached during text extraction: {full_path}"
                        )
                        break
                    if text_chunk.strip():
                        self.process_text(text_chunk, full_path, _deadline=deadline)

            if self.config.verbose:
                self.config.logger.debug(f"Successfully processed: {full_path}")

            return True

        except docx.opc.exceptions.PackageNotFoundError:
            error_msg = "DOCX Empty Or Protected"
            self.config.logger.warning(f"{error_msg}: {full_path}")
            self._add_error(error_msg, full_path, error_callback)
            return False
        except UnicodeDecodeError:
            error_msg = "Unicode Decode Error"
            self.config.logger.warning(f"{error_msg}: {full_path}")
            self._add_error(error_msg, full_path, error_callback)
            return False
        except PermissionError:
            error_msg = "Permission denied"
            self.config.logger.warning(f"{error_msg}: {full_path}")
            self._add_error(error_msg, full_path, error_callback)
            return False
        except FileNotFoundError:
            error_msg = "File not found"
            self.config.logger.warning(f"{error_msg}: {full_path}")
            self._add_error(error_msg, full_path, error_callback)
            return False
        except Exception as excpt:
            error_msg = f"Unexpected error: {type(excpt).__name__}: {str(excpt)}"
            self.config.logger.error(
                f"{error_msg}: {full_path}", exc_info=self.config.verbose
            )
            self._add_error(error_msg, full_path, error_callback)
            return False

    def _vector_triage_pass(self, text: str) -> bool:
        """Return True if the vector engine detects a PII signal in *text*.

        Used as a cheap pre-filter when ``config.use_vector_triage`` is True.
        If the vector engine is not available the method returns True so that
        other engines are not inadvertently skipped.
        """
        for engine in self.engines:
            if engine.name == "vector-search":
                return engine.triage_pass(text)  # type: ignore[attr-defined]
        # Vector engine not loaded – be conservative and let others run
        return True

    def finalize(self) -> None:
        """Run post-scan finalisation for all engines that support it.

        Currently used by VectorEngine to persist the FAISS index when
        ``--vector-save-index`` is configured.
        """
        for engine in self.engines:
            if hasattr(engine, "finalize"):
                try:
                    engine.finalize()
                except Exception as exc:
                    self.config.logger.warning(
                        f"Engine '{engine.name}' finalize error: {exc}"
                    )

    def _add_error(
        self,
        msg: str,
        path: str,
        error_callback: Optional[Callable[[str, str], None]] = None,
    ) -> None:
        """Add an error message.

        Args:
            msg: Error message
            path: File path where error occurred
            error_callback: Optional callback function for error reporting
        """
        if error_callback:
            error_callback(msg, path)
