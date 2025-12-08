"""Integration tests for magic number detection."""

from pathlib import Path
from unittest.mock import Mock

import pytest

from core.scanner import FileScanner, FileInfo
from config import Config


class TestMagicDetectionIntegration:
    """Integration tests for magic number detection."""

    @pytest.fixture
    def config_with_magic(self):
        """Create config with magic detection enabled."""
        config = Mock(spec=Config)
        config.use_magic_detection = True
        config.magic_detection_fallback = True
        config.verbose = False
        config.stop_count = None
        config.logger = Mock()
        config.logger.debug = Mock()
        config.logger.warning = Mock()
        config.logger.error = Mock()
        config.logger.info = Mock()

        def validate_file_path(path):
            return True, None

        config.validate_file_path = validate_file_path
        config.max_file_size_mb = 500.0

        return config

    @pytest.fixture
    def config_without_magic(self):
        """Create config without magic detection."""
        config = Mock(spec=Config)
        config.use_magic_detection = False
        config.magic_detection_fallback = False
        config.verbose = False
        config.stop_count = None
        config.logger = Mock()
        config.logger.debug = Mock()
        config.logger.warning = Mock()
        config.logger.error = Mock()
        config.logger.info = Mock()

        def validate_file_path(path):
            return True, None

        config.validate_file_path = validate_file_path
        config.max_file_size_mb = 500.0

        return config

    def test_scanner_with_magic_detection(self, config_with_magic, temp_dir):
        """Test scanner uses magic detection when enabled."""
        # Create a file without extension
        test_file = Path(temp_dir) / "testfile"
        test_file.write_text("test content")

        scanner = FileScanner(config_with_magic)
        assert scanner.file_type_detector is not None
        assert scanner.file_type_detector.enabled is True

        # Scan should work
        result = scanner.scan(temp_dir)
        assert result.total_files_found >= 1

    def test_scanner_without_magic_detection(self, config_without_magic, temp_dir):
        """Test scanner doesn't use magic detection when disabled."""
        scanner = FileScanner(config_without_magic)
        assert (
            scanner.file_type_detector is None
            or scanner.file_type_detector.enabled is False
        )

    def test_file_info_has_mime_type(self, config_with_magic, temp_dir):
        """Test that FileInfo includes MIME type when magic detection is used."""
        test_file = Path(temp_dir) / "test.txt"
        test_file.write_text("test content")

        scanner = FileScanner(config_with_magic)
        file_infos = []

        def collect_file_info(file_info: FileInfo):
            file_infos.append(file_info)

        scanner.scan(temp_dir, file_callback=collect_file_info)

        if file_infos:
            # MIME type might be None if detection libraries not available
            # but the attribute should exist
            assert hasattr(file_infos[0], "mime_type")

    def test_magic_detection_fallback(self, config_with_magic, temp_dir):
        """Test magic detection as fallback for files without extension."""
        # Create file without extension
        test_file = Path(temp_dir) / "noextension"
        test_file.write_text("test content")

        scanner = FileScanner(config_with_magic)
        file_infos = []

        def collect_file_info(file_info: FileInfo):
            file_infos.append(file_info)

        scanner.scan(temp_dir, file_callback=collect_file_info)

        # Should have found the file
        assert len(file_infos) >= 1
        # Extension might be inferred from MIME type
        assert file_infos[0].extension == "" or file_infos[0].extension == ".txt"
