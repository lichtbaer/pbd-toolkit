"""Tests for image processor."""

from pathlib import Path


from file_processors.image_processor import ImageProcessor


class TestImageProcessor:
    """Tests for ImageProcessor class."""

    def test_processor_initialization(self):
        """Test ImageProcessor can be initialized."""
        processor = ImageProcessor()
        assert processor is not None

    def test_can_process_by_extension_jpg(self):
        """Test can_process with .jpg extension."""
        assert ImageProcessor.can_process(".jpg") is True
        assert ImageProcessor.can_process(".JPG") is True
        assert ImageProcessor.can_process(".jpeg") is True

    def test_can_process_by_extension_png(self):
        """Test can_process with .png extension."""
        assert ImageProcessor.can_process(".png") is True
        assert ImageProcessor.can_process(".PNG") is True

    def test_can_process_by_extension_other(self):
        """Test can_process with other image extensions."""
        assert ImageProcessor.can_process(".gif") is True
        assert ImageProcessor.can_process(".bmp") is True
        assert ImageProcessor.can_process(".tiff") is True
        assert ImageProcessor.can_process(".webp") is True

    def test_can_process_by_mime_type(self):
        """Test can_process with MIME type."""
        assert ImageProcessor.can_process("", "", "image/jpeg") is True
        assert ImageProcessor.can_process("", "", "image/png") is True
        assert ImageProcessor.can_process("", "", "image/gif") is True
        assert ImageProcessor.can_process("", "", "text/plain") is False

    def test_can_process_non_image(self):
        """Test can_process returns False for non-images."""
        assert ImageProcessor.can_process(".txt") is False
        assert ImageProcessor.can_process(".pdf") is False
        assert ImageProcessor.can_process("", "", "text/plain") is False

    def test_get_image_mime_type(self):
        """Test getting MIME type from extension."""
        processor = ImageProcessor()

        assert processor.get_image_mime_type("test.jpg") == "image/jpeg"
        assert processor.get_image_mime_type("test.jpeg") == "image/jpeg"
        assert processor.get_image_mime_type("test.png") == "image/png"
        assert processor.get_image_mime_type("test.gif") == "image/gif"
        assert processor.get_image_mime_type("test.bmp") == "image/bmp"
        assert processor.get_image_mime_type("test.tiff") == "image/tiff"
        assert processor.get_image_mime_type("test.webp") == "image/webp"
        assert processor.get_image_mime_type("test.unknown") is None

    def test_extract_text_returns_empty(self, temp_dir):
        """Test extract_text returns empty string for images."""
        processor = ImageProcessor()
        # Create a dummy file (not a real image, but tests the method)
        test_file = Path(temp_dir) / "test.jpg"
        test_file.write_bytes(b"fake image data")

        result = processor.extract_text(str(test_file))
        assert result == ""

    def test_get_image_base64_nonexistent(self):
        """Test get_image_base64 with nonexistent file."""
        processor = ImageProcessor()
        result = processor.get_image_base64("/nonexistent/file.jpg")
        assert result is None

    def test_get_image_base64_valid_file(self, temp_dir):
        """Test get_image_base64 with valid file."""
        processor = ImageProcessor()
        test_file = Path(temp_dir) / "test.jpg"
        test_file.write_bytes(b"fake image data")

        result = processor.get_image_base64(str(test_file))
        assert result is not None
        assert isinstance(result, str)
        # Base64 encoded data should be a string
        assert len(result) > 0
