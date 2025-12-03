"""Statistics tracking for PII analysis."""

import datetime
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class NerStats:
    """Statistics for NER processing."""
    total_chunks_processed: int = 0
    total_entities_found: int = 0
    total_processing_time: float = 0.0
    entities_by_type: dict[str, int] = field(default_factory=dict)
    errors: int = 0


@dataclass
class Statistics:
    """Central statistics tracking for PII analysis.
    
    This class tracks:
    - File scanning statistics
    - Processing statistics
    - NER statistics
    - Performance metrics
    - Timing information
    """
    
    # File statistics
    total_files_found: int = 0
    files_processed: int = 0
    extension_counts: dict[str, int] = field(default_factory=dict)
    
    # Processing statistics
    matches_found: int = 0
    total_errors: int = 0
    errors_by_type: dict[str, int] = field(default_factory=dict)
    
    # NER statistics
    ner_stats: NerStats = field(default_factory=NerStats)
    
    # Timing
    start_time: Optional[datetime.datetime] = None
    end_time: Optional[datetime.datetime] = None
    
    def start(self) -> None:
        """Start timing."""
        self.start_time = datetime.datetime.now()
    
    def stop(self) -> None:
        """Stop timing."""
        self.end_time = datetime.datetime.now()
    
    @property
    def duration(self) -> datetime.timedelta:
        """Get duration of analysis.
        
        Returns:
            Duration as timedelta, or zero if not started/stopped
        """
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return datetime.timedelta(0)
    
    @property
    def duration_seconds(self) -> float:
        """Get duration in seconds.
        
        Returns:
            Duration in seconds, or 0.0 if not started/stopped
        """
        return max(self.duration.total_seconds(), 0.001)  # Avoid division by zero
    
    @property
    def files_per_second(self) -> float:
        """Calculate files processed per second.
        
        Returns:
            Throughput in files per second, or 0.0 if no files processed
        """
        if self.files_processed == 0 or self.duration_seconds == 0:
            return 0.0
        return round(self.files_processed / self.duration_seconds, 2)
    
    @property
    def avg_ner_time_per_chunk(self) -> float:
        """Calculate average NER processing time per chunk.
        
        Returns:
            Average time in seconds, or 0.0 if no chunks processed
        """
        if self.ner_stats.total_chunks_processed == 0:
            return 0.0
        return self.ner_stats.total_processing_time / self.ner_stats.total_chunks_processed
    
    def add_file_found(self, extension: str) -> None:
        """Record that a file was found.
        
        Args:
            extension: File extension (e.g., '.pdf', '.txt')
        """
        self.total_files_found += 1
        self.extension_counts[extension] = self.extension_counts.get(extension, 0) + 1
    
    def add_file_processed(self) -> None:
        """Record that a file was processed."""
        self.files_processed += 1
    
    def add_match(self) -> None:
        """Record that a PII match was found."""
        self.matches_found += 1
    
    def add_error(self, error_type: str) -> None:
        """Record an error.
        
        Args:
            error_type: Type/category of error
        """
        self.total_errors += 1
        self.errors_by_type[error_type] = self.errors_by_type.get(error_type, 0) + 1
    
    def update_from_scan_result(self, total_files: int, files_processed: int, 
                                extension_counts: dict[str, int],
                                errors: dict[str, list[str]]) -> None:
        """Update statistics from scan result.
        
        Args:
            total_files: Total number of files found
            files_processed: Number of files processed
            extension_counts: Dictionary mapping extensions to counts
            errors: Dictionary mapping error types to file lists
        """
        self.total_files_found = total_files
        self.files_processed = files_processed
        self.extension_counts = extension_counts.copy()
        
        # Count errors (count files, not error types)
        for error_type, file_list in errors.items():
            self.errors_by_type[error_type] = len(file_list)
            self.total_errors += len(file_list)
    
    def get_summary_dict(self) -> dict:
        """Get summary as dictionary for output.
        
        Returns:
            Dictionary with all statistics
        """
        return {
            "files_scanned": self.total_files_found,
            "files_analyzed": self.files_processed,
            "matches_found": self.matches_found,
            "errors": self.total_errors,
            "throughput_files_per_sec": self.files_per_second,
            "file_extensions": dict(sorted(
                self.extension_counts.items(), 
                key=lambda item: item[1], 
                reverse=True
            )),
            "ner_statistics": {
                "chunks_processed": self.ner_stats.total_chunks_processed,
                "entities_found": self.ner_stats.total_entities_found,
                "total_processing_time": self.ner_stats.total_processing_time,
                "avg_time_per_chunk": self.avg_ner_time_per_chunk,
                "entities_by_type": self.ner_stats.entities_by_type,
                "errors": self.ner_stats.errors
            } if self.ner_stats.total_chunks_processed > 0 else None
        }
