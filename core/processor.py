"""Text and file processing for PII detection."""

import threading
import time
from typing import Callable, Optional

import docx.opc.exceptions

from config import Config
from core.scanner import FileInfo
from core.statistics import Statistics
from core.engines import EngineRegistry
from core.engines.base import DetectionEngine
from file_processors import FileProcessorRegistry, PdfProcessor
from file_processors.image_processor import ImageProcessor
from matches import PiiMatchContainer


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

        # Initialize engines from registry
        self.engines: list[DetectionEngine] = []
        enabled_engines = self._get_enabled_engines()

        for engine_name in enabled_engines:
            engine = EngineRegistry.get_engine(engine_name, config)
            if engine and engine.is_available():
                self.engines.append(engine)
                if config.verbose:
                    config.logger.debug(f"Engine '{engine_name}' loaded and enabled")

        # Thread locks for thread-safe operations
        self._process_lock = threading.Lock()
        # Separate locks for each engine (some may not be thread-safe)
        self._engine_locks: dict[str, threading.Lock] = {
            engine.name: threading.Lock() for engine in self.engines
        }

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

    def process_text(self, text: str, file_path: str) -> None:
        """Process text content with all enabled detection engines.

        Args:
            text: Text content to analyze
            file_path: Path to the file containing the text
        """
        if not text.strip():
            return

        # Clean text to remove control characters that might confuse NLP models (especially spaCy)
        # Keep newlines, tabs and carriage returns, remove other non-printables
        text = "".join(ch for ch in text if ch.isprintable() or ch in "\n\t\r")

        if not text.strip():
            return

        if self.config.verbose:
            # Log a snippet of the text to debug extraction quality
            snippet = text[:100].replace("\n", "\\n")
            self.config.logger.debug(
                f"Processing text from {file_path} (len={len(text)}): '{snippet}...'"
            )

        all_results = []

        # Run all enabled engines
        for engine in self.engines:
            start_time = time.time()
            try:
                # Get appropriate lock for this engine
                engine_lock = self._engine_locks.get(engine.name, self._process_lock)

                with engine_lock:
                    results = engine.detect(text, self.config.ner_labels)

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
                        self.config.ner_stats.total_chunks_processed += 1
                        self.config.ner_stats.total_processing_time += processing_time
                        self.config.ner_stats.total_entities_found += len(results)

                        if self.statistics:
                            self.statistics.ner_stats.total_chunks_processed += 1
                            self.statistics.ner_stats.total_processing_time += (
                                processing_time
                            )
                            self.statistics.ner_stats.total_entities_found += len(
                                results
                            )

                        # Count entities by type
                        for result in results:
                            entity_type = result.entity_type
                            self.config.ner_stats.entities_by_type[entity_type] = (
                                self.config.ner_stats.entities_by_type.get(
                                    entity_type, 0
                                )
                                + 1
                            )

                            if self.statistics:
                                self.statistics.ner_stats.entities_by_type[
                                    entity_type
                                ] = (
                                    self.statistics.ner_stats.entities_by_type.get(
                                        entity_type, 0
                                    )
                                    + 1
                                )

            except RuntimeError as e:
                # GPU/Model-specific errors
                if engine.name == "gliner":
                    self.config.ner_stats.errors += 1
                    if self.statistics:
                        self.statistics.ner_stats.errors += 1
                self.config.logger.warning(
                    f"Engine '{engine.name}' processing error for {file_path}: {e}"
                )
                self._add_error(f"{engine.name} processing error", file_path)
            except MemoryError:
                # Memory issues
                if engine.name == "gliner":
                    self.config.ner_stats.errors += 1
                    if self.statistics:
                        self.statistics.ner_stats.errors += 1
                self.config.logger.error(
                    f"Out of memory during {engine.name} processing: {file_path}"
                )
                self._add_error(f"{engine.name} memory error", file_path)
            except Exception as e:
                # Unexpected errors
                if engine.name == "gliner":
                    self.config.ner_stats.errors += 1
                    if self.statistics:
                        self.statistics.ner_stats.errors += 1
                self.config.logger.error(
                    f"Unexpected {engine.name} error for {file_path}: {type(e).__name__}: {e}",
                    exc_info=self.config.verbose,
                )
                self._add_error(f"{engine.name} error: {type(e).__name__}", file_path)

        # Add all results to match container
        if all_results:
            with self._process_lock:
                self.match_container.add_detection_results(all_results, file_path)

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
        full_path = file_info.path
        ext = file_info.extension
        mime_type = getattr(file_info, "mime_type", None) or ""

        # Get appropriate processor for this file type
        processor = FileProcessorRegistry.get_processor(ext, full_path, mime_type)

        if processor is None:
            if self.config.verbose:
                self.config.logger.debug(f"Skipping unsupported file type: {full_path}")
            return False

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
                        results = pydantic_ai_engine.detect(
                            "", self.config.ner_labels, image_path=full_path
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

            # PDF processor yields text chunks, others return full text
            if isinstance(processor, PdfProcessor):
                for text_chunk in processor.extract_text(full_path):
                    if text_chunk.strip():  # Only process non-empty chunks
                        self.process_text(text_chunk, full_path)
            else:
                text = processor.extract_text(full_path)
                if text.strip():  # Only process if there's actual text
                    self.process_text(text, full_path)

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
