"""Pytest configuration and shared fixtures."""

from unittest.mock import Mock

import os
import tempfile

import pytest
from config import Config, NerStats


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def sample_text_file(temp_dir):
    """Create a sample text file for testing."""
    file_path = os.path.join(temp_dir, "test.txt")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(
            "This is a test file with email test@example.com and IBAN DE89 3704 0044 0532 0130 00."
        )
    return file_path


@pytest.fixture
def sample_html_file(temp_dir):
    """Create a sample HTML file for testing."""
    file_path = os.path.join(temp_dir, "test.html")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(
            """
        <html>
        <body>
            <p>Contact: user@example.com</p>
            <p>IBAN: DE89 3704 0044 0532 0130 00</p>
        </body>
        </html>
        """
        )
    return file_path


@pytest.fixture
def empty_whitelist():
    """Return an empty whitelist."""
    return []


@pytest.fixture
def sample_whitelist():
    """Return a sample whitelist."""
    return ["test@example.com", "info@"]


@pytest.fixture
def mock_config():
    """Create a mock Config object for testing."""
    config = Mock(spec=Config)
    config.verbose = False
    config.stop_count = None
    config.logger = Mock()
    config.logger.debug = Mock()
    config.logger.warning = Mock()
    config.logger.error = Mock()
    config.logger.info = Mock()

    # Defaults used by engines/processor
    config.use_regex = False
    config.use_ner = False
    config.use_spacy_ner = False
    config.use_ollama = False
    config.use_openai_compatible = False
    config.use_multimodal = False
    config.use_pydantic_ai = False

    config.regex_pattern = None
    config.ner_model = None
    config.ner_labels = []
    config.ner_threshold = 0.5
    config.ner_stats = NerStats()

    # Mock validate_file_path to always return valid
    def validate_file_path(path):
        return True, None

    config.validate_file_path = validate_file_path
    config.max_file_size_mb = 500.0

    return config
