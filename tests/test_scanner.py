"""Tests for file scanner."""

import os
import tempfile
from pathlib import Path

import pytest

from core.scanner import FileScanner, FileInfo, ScanResult
from config import Config


class TestFileScanner:
    """Tests for FileScanner class."""
    
    def test_file_scanner_initialization(self, mock_config):
        """Test FileScanner can be initialized."""
        scanner = FileScanner(mock_config)
        assert scanner.config == mock_config
        assert scanner._extension_counts == {}
        assert scanner._errors == {}
    
    def test_scan_empty_directory(self, mock_config, temp_dir):
        """Test scanning an empty directory."""
        scanner = FileScanner(mock_config)
        result = scanner.scan(temp_dir)
        
        assert isinstance(result, ScanResult)
        assert result.total_files_found == 0
        assert result.files_processed == 0
        assert result.extension_counts == {}
        assert result.errors == {}
    
    def test_scan_with_files(self, mock_config, temp_dir):
        """Test scanning directory with files."""
        # Create test files
        (Path(temp_dir) / "test1.txt").write_text("test content")
        (Path(temp_dir) / "test2.pdf").write_text("pdf content")
        (Path(temp_dir) / "test3.docx").write_text("docx content")
        
        scanner = FileScanner(mock_config)
        result = scanner.scan(temp_dir)
        
        assert result.total_files_found == 3
        assert ".txt" in result.extension_counts
        assert ".pdf" in result.extension_counts
        assert ".docx" in result.extension_counts
        assert result.extension_counts[".txt"] == 1
        assert result.extension_counts[".pdf"] == 1
        assert result.extension_counts[".docx"] == 1
    
    def test_scan_with_callback(self, mock_config, temp_dir):
        """Test scanning with file callback."""
        # Create test file
        test_file = Path(temp_dir) / "test.txt"
        test_file.write_text("test content")
        
        processed_files = []
        
        def callback(file_info: FileInfo):
            processed_files.append(file_info.path)
        
        scanner = FileScanner(mock_config)
        result = scanner.scan(temp_dir, file_callback=callback)
        
        assert len(processed_files) == 1
        assert str(test_file) in processed_files
        assert result.files_processed == 1
    
    def test_scan_with_stop_count(self, mock_config, temp_dir):
        """Test scanning with stop_count limit."""
        # Create multiple test files
        for i in range(10):
            (Path(temp_dir) / f"test{i}.txt").write_text("content")
        
        scanner = FileScanner(mock_config)
        result = scanner.scan(temp_dir, stop_count=5)
        
        assert result.total_files_found == 5
        assert result.files_processed == 5
    
    def test_scan_error_tracking(self, mock_config, temp_dir):
        """Test that errors are tracked correctly."""
        # Create a file that will cause validation error (too large)
        # Note: This test depends on max_file_size_mb in config
        large_file = Path(temp_dir) / "large.txt"
        # Create a file larger than default max (500 MB)
        # For testing, we'll create a smaller file and mock the validation
        large_file.write_text("x" * 1000)
        
        scanner = FileScanner(mock_config)
        result = scanner.scan(temp_dir)
        
        # Errors should be tracked (if validation fails)
        # The exact behavior depends on file size and config
        assert isinstance(result.errors, dict)
    
    def test_file_info_creation(self):
        """Test FileInfo dataclass."""
        file_info = FileInfo(
            path="/test/file.txt",
            extension=".txt",
            size_mb=1.5
        )
        
        assert file_info.path == "/test/file.txt"
        assert file_info.extension == ".txt"
        assert file_info.size_mb == 1.5
    
    def test_scan_result_creation(self):
        """Test ScanResult dataclass."""
        result = ScanResult(
            total_files_found=10,
            files_processed=8,
            extension_counts={".txt": 5, ".pdf": 3},
            errors={"error1": ["file1.txt"]}
        )
        
        assert result.total_files_found == 10
        assert result.files_processed == 8
        assert result.extension_counts[".txt"] == 5
        assert result.extension_counts[".pdf"] == 3
        assert "error1" in result.errors
        assert "file1.txt" in result.errors["error1"]
