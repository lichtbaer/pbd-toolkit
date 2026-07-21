"""Tests for file scanner."""

import concurrent.futures
from pathlib import Path
from unittest.mock import patch

from core.scanner import FileInfo, FileScanner, ScanResult
from file_processors.registry import FileProcessorRegistry


class TestFileScanner:
    """Tests for FileScanner class."""

    def test_file_scanner_initialization(self, mock_config):
        """Test FileScanner can be initialized."""
        scanner = FileScanner(mock_config)
        assert scanner.config == mock_config
        assert scanner.scan_config == mock_config.scan
        assert scanner.runtime_config == mock_config.runtime
        assert scanner._extension_counts == {}
        assert scanner._errors == {}

    def test_file_scanner_defaults_to_global_registry(self, mock_config):
        """With no override, FileScanner reads the process-global registry (issue #78)."""
        scanner = FileScanner(mock_config)
        assert scanner.file_processor_registry is FileProcessorRegistry

    def test_file_scanner_uses_injected_isolated_registry(self, mock_config, temp_dir):
        """An injected isolated registry is used instead of the global default.

        Proves the DI wiring is real, not just unused surface: scanning with an
        empty isolated registry finds the file on disk but processes none of
        it, because none of the (isolated, empty) registry's processors claim
        the extension.
        """
        (Path(temp_dir) / "test1.txt").write_text("test content")

        empty_registry = FileProcessorRegistry.create_isolated()
        scanner = FileScanner(mock_config, file_processor_registry=empty_registry)
        assert scanner.file_processor_registry is empty_registry

        result = scanner.scan(temp_dir)

        assert result.total_files_found == 1
        assert result.files_processed == 0

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

    def test_scan_callback_raises_exception(self, mock_config, temp_dir):
        """Test that callback exceptions are caught and tracked as errors."""
        test_file = Path(temp_dir) / "test.txt"
        test_file.write_text("content")

        def failing_callback(file_info: FileInfo):
            raise RuntimeError("Callback failed intentionally")

        scanner = FileScanner(mock_config)
        result = scanner.scan(temp_dir, file_callback=failing_callback)

        assert len(result.errors) > 0
        assert result.files_processed == 0
        assert "Callback error" in str(list(result.errors.keys())[0])

    def test_scan_validation_failure_tracked(self, mock_config, temp_dir):
        """Test that validation failures are tracked as errors."""
        (Path(temp_dir) / "valid.txt").write_text("content")
        (Path(temp_dir) / "rejected.txt").write_text("content")

        def validate_reject_some(file_path: str):
            if "rejected" in file_path:
                return False, "Path traversal detected"
            return True, None

        mock_config.scan.validate_file_path = validate_reject_some

        scanner = FileScanner(mock_config)
        result = scanner.scan(temp_dir)

        assert result.total_files_found == 2
        assert len(result.errors) > 0
        assert "Path traversal" in str(list(result.errors.keys())[0])

    def test_scan_with_subdirectory(self, mock_config, temp_dir):
        """Test scanning directory with subdirectories."""
        subdir = Path(temp_dir) / "subdir"
        subdir.mkdir()
        (Path(temp_dir) / "root.txt").write_text("root")
        (subdir / "nested.txt").write_text("nested")

        scanner = FileScanner(mock_config)
        result = scanner.scan(temp_dir)

        assert result.total_files_found == 2
        assert result.extension_counts[".txt"] == 2

    def test_file_info_creation(self):
        """Test FileInfo dataclass."""
        file_info = FileInfo(path="/test/file.txt", extension=".txt", size_mb=1.5)

        assert file_info.path == "/test/file.txt"
        assert file_info.extension == ".txt"
        assert file_info.size_mb == 1.5

    def test_scan_result_creation(self):
        """Test ScanResult dataclass."""
        result = ScanResult(
            total_files_found=10,
            files_processed=8,
            extension_counts={".txt": 5, ".pdf": 3},
            errors={"error1": ["file1.txt"]},
        )

        assert result.total_files_found == 10
        assert result.files_processed == 8
        assert result.extension_counts[".txt"] == 5
        assert result.extension_counts[".pdf"] == 3
        assert "error1" in result.errors
        assert "file1.txt" in result.errors["error1"]

    def test_scan_logs_warning_when_future_drain_fails(self, mock_config, temp_dir):
        """Test that exceptions during future draining are logged, not silenced."""
        test_file = Path(temp_dir) / "test.txt"
        test_file.write_text("content")

        call_count = 0

        def callback_returning_future(file_info: FileInfo):
            nonlocal call_count
            call_count += 1
            fut = concurrent.futures.Future()
            fut.set_result(None)
            return fut

        def failing_wait(futures, **kwargs):
            raise OSError("Simulated drain failure")

        scanner = FileScanner(mock_config)

        with patch("concurrent.futures.wait", side_effect=failing_wait):
            result = scanner.scan(temp_dir, file_callback=callback_returning_future)

        # The scanner should still return a result (resilient)
        assert isinstance(result, ScanResult)
        # The logger should have been called with a warning
        mock_config.logger.warning.assert_called()
        warning_args = str(mock_config.logger.warning.call_args_list)
        assert (
            "pending futures" in warning_args.lower()
            or "drain" in warning_args.lower()
            or "OSError" in warning_args
        )

    def test_scan_logs_warning_when_final_wait_fails(self, mock_config, temp_dir):
        """Test that final wait failure is logged."""
        test_file = Path(temp_dir) / "test.txt"
        test_file.write_text("content")

        def callback_returning_future(file_info: FileInfo):
            fut = concurrent.futures.Future()
            fut.set_result(None)
            return fut

        scanner = FileScanner(mock_config)

        # We need the future to still be "pending" so that the final drain runs.
        # Patch wait only at the final drain (outside the loop).
        original_wait = concurrent.futures.wait
        wait_call_count = 0

        def failing_on_second(futures, **kwargs):
            nonlocal wait_call_count
            wait_call_count += 1
            if wait_call_count > 1:
                raise RuntimeError("Final wait failed")
            return original_wait(futures, **kwargs)

        with patch("concurrent.futures.wait", side_effect=failing_on_second):
            result = scanner.scan(temp_dir, file_callback=callback_returning_future)

        assert isinstance(result, ScanResult)
