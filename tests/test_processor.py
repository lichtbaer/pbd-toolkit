"""Tests for text processor."""

import re
from unittest.mock import Mock, patch


from core.processor import TextProcessor
from config import NerStats
from matches import PiiMatchContainer


class TestTextProcessor:
    """Tests for TextProcessor class."""

    def test_text_processor_initialization(self, mock_config):
        """Test TextProcessor can be initialized."""
        pmc = PiiMatchContainer()
        processor = TextProcessor(mock_config, pmc)

        assert processor.config == mock_config
        assert processor.match_container == pmc
        assert processor._process_lock is not None
        assert processor._ner_lock is not None

    def test_process_text_with_regex(self, mock_config):
        """Test processing text with regex detection."""
        pmc = PiiMatchContainer()
        processor = TextProcessor(mock_config, pmc)

        # Setup regex pattern
        mock_config.use_regex = True
        mock_config.regex_pattern = re.compile(
            r"\b\w+@\w+\.\w+\b"
        )  # Simple email pattern

        text = "Contact me at test@example.com for more info."
        processor.process_text(text, "/test/file.txt")

        # Should have found at least one match
        assert len(pmc.pii_matches) > 0

    def test_process_text_without_regex(self, mock_config):
        """Test processing text without regex enabled."""
        pmc = PiiMatchContainer()
        processor = TextProcessor(mock_config, pmc)

        mock_config.use_regex = False
        mock_config.regex_pattern = None

        text = "Contact me at test@example.com"
        processor.process_text(text, "/test/file.txt")

        # Should not have found matches (regex disabled)
        assert len(pmc.pii_matches) == 0

    @patch("core.processor.time.time")
    def test_process_text_with_ner(self, mock_time, mock_config):
        """Test processing text with NER detection."""
        pmc = PiiMatchContainer()
        processor = TextProcessor(mock_config, pmc)

        # Setup NER model
        mock_config.use_ner = True
        mock_ner_model = Mock()
        mock_ner_model.predict_entities = Mock(
            return_value=[{"text": "John Doe", "label": "person", "score": 0.9}]
        )
        mock_config.ner_model = mock_ner_model
        mock_config.ner_labels = ["person"]
        mock_config.ner_threshold = 0.5
        mock_config.ner_stats = NerStats()

        mock_time.side_effect = [0.0, 0.1]  # start_time, end_time

        text = "John Doe is a person."
        processor.process_text(text, "/test/file.txt")

        # Should have found NER match
        assert len(pmc.pii_matches) > 0
        assert mock_config.ner_stats.total_chunks_processed == 1

    def test_process_text_ner_error_handling(self, mock_config):
        """Test NER error handling."""
        pmc = PiiMatchContainer()
        processor = TextProcessor(mock_config, pmc)

        mock_config.use_ner = True
        mock_ner_model = Mock()
        mock_ner_model.predict_entities = Mock(side_effect=RuntimeError("GPU error"))
        mock_config.ner_model = mock_ner_model
        mock_config.ner_labels = ["person"]
        mock_config.ner_threshold = 0.5
        mock_config.ner_stats = NerStats()

        text = "Some text"
        processor.process_text(text, "/test/file.txt")

        # Should have recorded error
        assert mock_config.ner_stats.errors == 1

    def test_process_file_unsupported_type(self, mock_config, temp_dir):
        """Test processing unsupported file type."""
        from pathlib import Path
        from core.scanner import FileInfo

        pmc = PiiMatchContainer()
        processor = TextProcessor(mock_config, pmc)

        # Create file with unsupported extension
        test_file = Path(temp_dir) / "test.xyz"
        test_file.write_text("content")

        file_info = FileInfo(path=str(test_file), extension=".xyz", size_mb=0.001)

        result = processor.process_file(file_info)

        # Should return False (not processed)
        assert result is False

    def test_process_file_success(self, mock_config, temp_dir):
        """Test successful file processing."""
        from pathlib import Path
        from core.scanner import FileInfo

        pmc = PiiMatchContainer()
        processor = TextProcessor(mock_config, pmc)

        # Create text file
        test_file = Path(temp_dir) / "test.txt"
        test_file.write_text("Contact: test@example.com")

        # Setup regex
        mock_config.use_regex = True
        mock_config.regex_pattern = re.compile(r"\b\w+@\w+\.\w+\b")

        file_info = FileInfo(path=str(test_file), extension=".txt", size_mb=0.001)

        result = processor.process_file(file_info)

        # Should return True (processed successfully)
        assert result is True
        assert len(pmc.pii_matches) > 0

    def test_process_file_with_error_callback(self, mock_config, temp_dir):
        """Test file processing with error callback."""
        from core.scanner import FileInfo

        pmc = PiiMatchContainer()
        processor = TextProcessor(mock_config, pmc)

        # Create file that will cause error (non-existent)
        file_info = FileInfo(
            path="/nonexistent/file.txt", extension=".txt", size_mb=0.001
        )

        errors_caught = []

        def error_callback(msg, path):
            errors_caught.append((msg, path))

        result = processor.process_file(file_info, error_callback=error_callback)

        # Should return False and call error callback
        assert result is False
        assert len(errors_caught) > 0
