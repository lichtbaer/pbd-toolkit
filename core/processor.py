"""Text and file processing for PII detection."""

import threading
import time
from typing import Callable, Optional

import docx.opc.exceptions

from config import Config
from core.exceptions import ProcessingError
from core.scanner import FileInfo
from core.statistics import Statistics
from file_processors import BaseFileProcessor, FileProcessorRegistry, PdfProcessor
from matches import PiiMatchContainer


class TextProcessor:
    """Processes text content for PII detection using regex and/or NER.
    
    This class handles:
    - Regex-based pattern matching
    - NER-based entity recognition
    - Statistics tracking
    - Error handling
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
        
        # Thread locks for thread-safe operations
        self._process_lock = threading.Lock()
        # Separate lock for NER model calls (GLiNER may not be thread-safe)
        self._ner_lock = threading.Lock()
    
    def process_text(self, text: str, file_path: str) -> None:
        """Process text content with regex and/or NER-based PII detection.
        
        Args:
            text: Text content to analyze
            file_path: Path to the file containing the text
        """
        if self.config.use_regex and self.config.regex_pattern:
            # Use finditer to find ALL matches, not just the first one
            for match in self.config.regex_pattern.finditer(text):
                with self._process_lock:
                    self.match_container.add_matches_regex(match, file_path)
        
        if self.config.use_ner and self.config.ner_model:
            start_time = time.time()
            try:
                # Serialize NER model calls to ensure thread-safety
                # GLiNER model may not be thread-safe, so we use a separate lock
                with self._ner_lock:
                    entities = self.config.ner_model.predict_entities(
                        text, self.config.ner_labels, threshold=self.config.ner_threshold
                    )
                processing_time = time.time() - start_time
                
                # Update statistics
                with self._process_lock:
                    # Update NER stats (backward compatibility with config.ner_stats)
                    self.config.ner_stats.total_chunks_processed += 1
                    self.config.ner_stats.total_processing_time += processing_time
                    self.config.ner_stats.total_entities_found += len(entities) if entities else 0
                    
                    # Update central statistics if available
                    if self.statistics:
                        self.statistics.ner_stats.total_chunks_processed += 1
                        self.statistics.ner_stats.total_processing_time += processing_time
                        self.statistics.ner_stats.total_entities_found += len(entities) if entities else 0
                    
                    # Count entities by type
                    if entities:
                        for entity in entities:
                            entity_type = entity.get("label", "unknown")
                            self.config.ner_stats.entities_by_type[entity_type] = \
                                self.config.ner_stats.entities_by_type.get(entity_type, 0) + 1
                            
                            if self.statistics:
                                self.statistics.ner_stats.entities_by_type[entity_type] = \
                                    self.statistics.ner_stats.entities_by_type.get(entity_type, 0) + 1
                    
                    self.match_container.add_matches_ner(entities, file_path)
            except RuntimeError as e:
                # GPU/Model-specific errors
                self.config.ner_stats.errors += 1
                if self.statistics:
                    self.statistics.ner_stats.errors += 1
                self.config.logger.warning(f"NER processing error for {file_path}: {e}")
                self._add_error("NER processing error", file_path)
            except MemoryError as e:
                # Memory issues
                self.config.ner_stats.errors += 1
                if self.statistics:
                    self.statistics.ner_stats.errors += 1
                self.config.logger.error(f"Out of memory during NER processing: {file_path}")
                self._add_error("NER memory error", file_path)
            except Exception as e:
                # Unexpected errors
                self.config.ner_stats.errors += 1
                if self.statistics:
                    self.statistics.ner_stats.errors += 1
                self.config.logger.error(
                    f"Unexpected NER error for {file_path}: {type(e).__name__}: {e}",
                    exc_info=self.config.verbose
                )
                self._add_error(f"NER error: {type(e).__name__}", file_path)
    
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
