"""Tests for file type detector."""

from pathlib import Path


from core.file_type_detector import FileTypeDetector


class TestFileTypeDetector:
    """Tests for FileTypeDetector class."""

    def test_detector_initialization_enabled(self):
        """Test detector can be initialized with enabled=True."""
        detector = FileTypeDetector(enabled=True)
        assert detector.enabled is True

    def test_detector_initialization_disabled(self):
        """Test detector can be initialized with enabled=False."""
        detector = FileTypeDetector(enabled=False)
        assert detector.enabled is False
        assert detector.detect_type("nonexistent") is None

    def test_detect_type_nonexistent_file(self):
        """Test detecting type of nonexistent file returns None."""
        detector = FileTypeDetector(enabled=True)
        result = detector.detect_type("/nonexistent/file.pdf")
        assert result is None

    def test_detect_type_text_file(self, temp_dir):
        """Test detecting type of text file."""
        detector = FileTypeDetector(enabled=True)
        test_file = Path(temp_dir) / "test.txt"
        test_file.write_text("test content")

        mime_type = detector.detect_type(str(test_file))
        # Should detect text/plain or return None if libraries not available
        if mime_type:
            assert mime_type == "text/plain" or mime_type.startswith("text/")

    def test_get_extension_from_mime(self):
        """Test getting extension from MIME type."""
        detector = FileTypeDetector(enabled=True)

        assert detector.get_extension_from_mime("application/pdf") == ".pdf"
        assert detector.get_extension_from_mime("text/html") == ".html"
        assert detector.get_extension_from_mime("image/jpeg") == ".jpg"
        assert detector.get_extension_from_mime("application/json") == ".json"
        assert detector.get_extension_from_mime("unknown/mime") is None

    def test_get_extension_from_mime_docx(self):
        """Test getting extension for DOCX MIME type."""
        detector = FileTypeDetector(enabled=True)
        mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        assert detector.get_extension_from_mime(mime) == ".docx"

    def test_is_available(self):
        """Test availability check."""
        detector = FileTypeDetector(enabled=True)
        # Should return True if at least one library is available, False otherwise
        # This depends on whether python-magic or filetype is installed
        result = detector.is_available()
        assert isinstance(result, bool)

    def test_detect_type_disabled(self, temp_dir):
        """Test that detection returns None when disabled."""
        detector = FileTypeDetector(enabled=False)
        test_file = Path(temp_dir) / "test.txt"
        test_file.write_text("test content")

        result = detector.detect_type(str(test_file))
        assert result is None
