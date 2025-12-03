"""Text and file processing for PII detection."""

import threading
import time
from typing import Callable, Optional

import docx.opc.exceptions

from config import Config
from core.exceptions import ProcessingError
from core.scanner import FileInfo
from core.statistics import Statistics
from core.engines import EngineRegistry
from core.engines.base import DetectionEngine
from file_processors import BaseFileProcessor, FileProcessorRegistry, PdfProcessor
from matches import PiiMatchContainer


class TextProcessor:
    """Processes text content for PII detection using multiple engines.
    
    This class handles:
    - Multiple detection engines (regex, GLiNER, spaCy, LLMs, etc.)
    - Statistics tracking
    - Error handling
    - Thread-safe operations
    """
    
    def __init__(self, config: Config, match_container: PiiMatchContainer, 
                 statistics: Optional[Statistics] = None):
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
        # Additional engines will be added via config.enabled_engines in future
        return engines
    
    def process_text(self, text: str, file_path: str) -> None:
        """Process text content with all enabled detection engines.
        
        Args:
            text: Text content to analyze
            file_path: Path to the file containing the text
        """
        if not text.strip():
            return
        
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
                
                # Update statistics for GLiNER (backward compatibility)
                if engine.name == "gliner":
                    with self._process_lock:
                        self.config.ner_stats.total_chunks_processed += 1
                        self.config.ner_stats.total_processing_time += processing_time
                        self.config.ner_stats.total_entities_found += len(results)
                        
                        if self.statistics:
                            self.statistics.ner_stats.total_chunks_processed += 1
                            self.statistics.ner_stats.total_processing_time += processing_time
                            self.statistics.ner_stats.total_entities_found += len(results)
                        
                        # Count entities by type
                        for result in results:
                            entity_type = result.entity_type
                            self.config.ner_stats.entities_by_type[entity_type] = \
                                self.config.ner_stats.entities_by_type.get(entity_type, 0) + 1
                            
                            if self.statistics:
                                self.statistics.ner_stats.entities_by_type[entity_type] = \
                                    self.statistics.ner_stats.entities_by_type.get(entity_type, 0) + 1
                
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
            except MemoryError as e:
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
                    exc_info=self.config.verbose
                )
                self._add_error(f"{engine.name} error: {type(e).__name__}", file_path)
        
        # Add all results to match container
        if all_results:
            with self._process_lock:
                self.match_container.add_detection_results(all_results, file_path)
    
    def process_file(self, file_info: FileInfo, error_callback: Optional[Callable[[str, str], None]] = None) -> bool:
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
        
        # Get appropriate processor for this file type
        processor = FileProcessorRegistry.get_processor(ext, full_path)
        
        if processor is None:
            if self.config.verbose:
                self.config.logger.debug(f"Skipping unsupported file type: {full_path}")
            return False
        
        try:
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
            self.config.logger.error(f"{error_msg}: {full_path}", exc_info=self.config.verbose)
            self._add_error(error_msg, full_path, error_callback)
            return False
    
    def _add_error(self, msg: str, path: str, error_callback: Optional[Callable[[str, str], None]] = None) -> None:
        """Add an error message.
        
        Args:
            msg: Error message
            path: File path where error occurred
            error_callback: Optional callback function for error reporting
        """
        if error_callback:
            error_callback(msg, path)
