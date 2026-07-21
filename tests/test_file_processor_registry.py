"""Tests for FileProcessorRegistry."""

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


class TestFileProcessorRegistryIsolation:
    """Tests for FileProcessorRegistry.create_isolated() / snapshot() (issue #78)."""

    def test_create_isolated_starts_empty_and_does_not_affect_global(self):
        isolated = FileProcessorRegistry.create_isolated()
        assert isolated.get_all_processors() == []

        class DummyProcessor(BaseFileProcessor):
            def extract_text(self, file_path: str):
                return ""

            @staticmethod
            def can_process(extension: str, file_path: str = "", mime_type: str = ""):
                return extension == ".dummy_isolated"

        isolated.register_class(DummyProcessor)
        assert isolated.get_processor(".dummy_isolated") is not None
        # The global, process-wide registry must be untouched.
        assert FileProcessorRegistry.get_processor(".dummy_isolated") is None

    def test_snapshot_is_a_copy_not_a_live_view(self):
        snapshot = FileProcessorRegistry.snapshot()
        assert len(snapshot.get_all_processors()) == len(
            FileProcessorRegistry.get_all_processors()
        )

        class DummyProcessor(BaseFileProcessor):
            def extract_text(self, file_path: str):
                return ""

            @staticmethod
            def can_process(extension: str, file_path: str = "", mime_type: str = ""):
                return extension == ".dummy_snapshot"

        # Registering on the snapshot must not affect the global registry.
        snapshot.register_class(DummyProcessor)
        assert FileProcessorRegistry.get_processor(".dummy_snapshot") is None

    def test_two_isolated_registries_do_not_leak_into_each_other(self):
        """One test's custom registry must not affect another (issue #78 test notes)."""

        class ProcessorA(BaseFileProcessor):
            def extract_text(self, file_path: str):
                return ""

            @staticmethod
            def can_process(extension: str, file_path: str = "", mime_type: str = ""):
                return extension == ".a_only"

        registry_1 = FileProcessorRegistry.create_isolated()
        registry_1.register_class(ProcessorA)

        registry_2 = FileProcessorRegistry.create_isolated()

        assert registry_1.get_processor(".a_only") is not None
        assert registry_2.get_processor(".a_only") is None
