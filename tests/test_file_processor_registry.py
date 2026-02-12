"""Tests for FileProcessorRegistry."""

import pytest

from file_processors import FileProcessorRegistry
from file_processors.base_processor import BaseFileProcessor


class TestFileProcessorRegistryGetProcessor:
    """Tests for FileProcessorRegistry.get_processor()."""

    def test_get_processor_by_extension_pdf(self):
        """Test get_processor returns processor for .pdf."""
        processor = FileProcessorRegistry.get_processor(".pdf")
        assert processor is not None
        assert processor.can_process(".pdf")

    def test_get_processor_by_extension_txt(self):
        """Test get_processor returns processor for .txt."""
        processor = FileProcessorRegistry.get_processor(".txt")
        assert processor is not None
        assert processor.can_process(".txt")

    def test_get_processor_by_extension_json(self):
        """Test get_processor returns processor for .json."""
        processor = FileProcessorRegistry.get_processor(".json")
        assert processor is not None
        assert processor.can_process(".json")

    def test_get_processor_returns_none_for_unknown_extension(self):
        """Test get_processor returns None for unsupported extension."""
        processor = FileProcessorRegistry.get_processor(".xyz")
        assert processor is None

    def test_get_processor_with_mime_type(self):
        """Test get_processor with mime_type parameter (e.g. ImageProcessor)."""
        processor = FileProcessorRegistry.get_processor(
            ".jpg", file_path="", mime_type="image/jpeg"
        )
        assert processor is not None

    def test_get_processor_with_file_path_for_text(self, temp_dir):
        """Test get_processor with file_path for text/plain detection."""
        from pathlib import Path

        test_file = Path(temp_dir) / "noext"
        test_file.write_text("content")
        processor = FileProcessorRegistry.get_processor(
            "", file_path=str(test_file), mime_type="text/plain"
        )
        assert processor is not None

    def test_get_processor_case_insensitive_extension(self):
        """Test get_processor handles extension case."""
        processor = FileProcessorRegistry.get_processor(".PDF")
        assert processor is not None
        processor2 = FileProcessorRegistry.get_processor(".TXT")
        assert processor2 is not None


class TestFileProcessorRegistryOtherMethods:
    """Tests for get_all_processors, get_supported_extensions, register, clear."""

    def test_get_all_processors(self):
        """Test get_all_processors returns list of processors."""
        processors = FileProcessorRegistry.get_all_processors()
        assert isinstance(processors, list)
        assert len(processors) > 0

    def test_get_supported_extensions(self):
        """Test get_supported_extensions returns sorted list."""
        extensions = FileProcessorRegistry.get_supported_extensions()
        assert isinstance(extensions, list)
        assert ".pdf" in extensions
        assert ".txt" in extensions
        assert extensions == sorted(extensions)

    def test_register_class_and_clear(self):
        """Test register_class and clear, then restore registry."""

        class DummyProcessor(BaseFileProcessor):
            def extract_text(self, file_path: str):
                return ""

            @staticmethod
            def can_process(extension: str, file_path: str = "", mime_type: str = ""):
                return extension == ".dummy"

        processors_before = FileProcessorRegistry.get_all_processors()
        try:
            FileProcessorRegistry.clear()
            assert len(FileProcessorRegistry.get_all_processors()) == 0

            FileProcessorRegistry.register_class(DummyProcessor)
            processor = FileProcessorRegistry.get_processor(".dummy")
            assert processor is not None
            assert processor.can_process(".dummy")
        finally:
            FileProcessorRegistry.clear()
            for p in processors_before:
                FileProcessorRegistry.register(p)
