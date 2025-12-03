"""Tests for statistics tracking."""

import datetime
import pytest

from core.statistics import Statistics, NerStats


class TestStatistics:
    """Tests for Statistics class."""
    
    def test_statistics_initialization(self):
        """Test Statistics can be initialized."""
        stats = Statistics()
        
        assert stats.total_files_found == 0
        assert stats.files_processed == 0
        assert stats.matches_found == 0
        assert stats.total_errors == 0
        assert stats.extension_counts == {}
        assert stats.errors_by_type == {}
        assert isinstance(stats.ner_stats, NerStats)
        assert stats.start_time is None
        assert stats.end_time is None
    
    def test_start_stop_timing(self):
        """Test start and stop timing."""
        stats = Statistics()
        
        stats.start()
        assert stats.start_time is not None
        assert isinstance(stats.start_time, datetime.datetime)
        
        stats.stop()
        assert stats.end_time is not None
        assert isinstance(stats.end_time, datetime.datetime)
        assert stats.end_time >= stats.start_time
    
    def test_duration(self):
        """Test duration calculation."""
        stats = Statistics()
        
        # Before start/stop
        assert stats.duration == datetime.timedelta(0)
        assert stats.duration_seconds == 0.001
        
        # After start/stop
        stats.start()
        import time
        time.sleep(0.1)  # Small delay
        stats.stop()
        
        assert stats.duration.total_seconds() > 0
        assert stats.duration_seconds > 0
    
    def test_files_per_second(self):
        """Test files per second calculation."""
        stats = Statistics()
        
        # No files processed
        assert stats.files_per_second == 0.0
        
        # With files processed
        stats.start()
        stats.files_processed = 10
        stats.stop()
        
        # Should calculate correctly
        assert stats.files_per_second > 0
    
    def test_add_file_found(self):
        """Test adding file found."""
        stats = Statistics()
        
        stats.add_file_found(".pdf")
        assert stats.total_files_found == 1
        assert stats.extension_counts[".pdf"] == 1
        
        stats.add_file_found(".txt")
        assert stats.total_files_found == 2
        assert stats.extension_counts[".txt"] == 1
        
        stats.add_file_found(".pdf")
        assert stats.total_files_found == 3
        assert stats.extension_counts[".pdf"] == 2
    
    def test_add_file_processed(self):
        """Test adding file processed."""
        stats = Statistics()
        
        stats.add_file_processed()
        assert stats.files_processed == 1
        
        stats.add_file_processed()
        assert stats.files_processed == 2
    
    def test_add_match(self):
        """Test adding match."""
        stats = Statistics()
        
        stats.add_match()
        assert stats.matches_found == 1
        
        stats.add_match()
        assert stats.matches_found == 2
    
    def test_add_error(self):
        """Test adding error."""
        stats = Statistics()
        
        stats.add_error("Permission denied")
        assert stats.total_errors == 1
        assert stats.errors_by_type["Permission denied"] == 1
        
        stats.add_error("File not found")
        assert stats.total_errors == 2
        assert stats.errors_by_type["File not found"] == 1
        
        stats.add_error("Permission denied")
        assert stats.total_errors == 3
        assert stats.errors_by_type["Permission denied"] == 2
    
    def test_update_from_scan_result(self):
        """Test updating from scan result."""
        stats = Statistics()
        
        extension_counts = {".pdf": 5, ".txt": 3, ".docx": 2}
        errors = {
            "Permission denied": ["file1.txt", "file2.pdf"],
            "File not found": ["file3.docx"]
        }
        
        stats.update_from_scan_result(
            total_files=10,
            files_processed=8,
            extension_counts=extension_counts,
            errors=errors
        )
        
        assert stats.total_files_found == 10
        assert stats.files_processed == 8
        assert stats.extension_counts[".pdf"] == 5
        assert stats.extension_counts[".txt"] == 3
        assert stats.extension_counts[".docx"] == 2
        assert stats.total_errors == 3  # 2 + 1
        assert stats.errors_by_type["Permission denied"] == 2
        assert stats.errors_by_type["File not found"] == 1
    
    def test_avg_ner_time_per_chunk(self):
        """Test average NER time per chunk calculation."""
        stats = Statistics()
        
        # No chunks processed
        assert stats.avg_ner_time_per_chunk == 0.0
        
        # With chunks
        stats.ner_stats.total_chunks_processed = 10
        stats.ner_stats.total_processing_time = 5.0
        
        assert stats.avg_ner_time_per_chunk == 0.5
    
    def test_get_summary_dict(self):
        """Test getting summary dictionary."""
        stats = Statistics()
        
        stats.total_files_found = 10
        stats.files_processed = 8
        stats.matches_found = 5
        stats.total_errors = 2
        stats.extension_counts = {".pdf": 5, ".txt": 3}
        stats.ner_stats.total_chunks_processed = 10
        stats.ner_stats.total_entities_found = 5
        
        summary = stats.get_summary_dict()
        
        assert summary["files_scanned"] == 10
        assert summary["files_analyzed"] == 8
        assert summary["matches_found"] == 5
        assert summary["errors"] == 2
        assert summary["throughput_files_per_sec"] >= 0
        assert ".pdf" in summary["file_extensions"]
        assert summary["ner_statistics"] is not None
        assert summary["ner_statistics"]["chunks_processed"] == 10


class TestNerStats:
    """Tests for NerStats class."""
    
    def test_ner_stats_initialization(self):
        """Test NerStats can be initialized."""
        ner_stats = NerStats()
        
        assert ner_stats.total_chunks_processed == 0
        assert ner_stats.total_entities_found == 0
        assert ner_stats.total_processing_time == 0.0
        assert ner_stats.entities_by_type == {}
        assert ner_stats.errors == 0
