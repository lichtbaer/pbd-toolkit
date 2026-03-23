"""Tests for setup and configuration."""

import json
from pathlib import Path


def _config_types_path() -> Path:
    """Path to packaged config_types.json (repo layout)."""
    return Path(__file__).resolve().parent.parent / "core" / "config_types.json"


class TestSetup:
    """Tests for setup functionality."""

    def test_constants_exist(self):
        """Test that constants are properly defined."""
        from core import constants

        assert hasattr(constants, "MIN_PDF_TEXT_LENGTH")
        assert hasattr(constants, "NER_THRESHOLD")
        assert hasattr(constants, "NER_MODEL_NAME")
        assert hasattr(constants, "CONFIG_FILE")
        assert hasattr(constants, "OUTPUT_DIR")
        assert hasattr(constants, "VERSION")

        # Check types
        assert isinstance(constants.MIN_PDF_TEXT_LENGTH, int)
        assert isinstance(constants.NER_THRESHOLD, float)
        assert isinstance(constants.NER_MODEL_NAME, str)
        assert isinstance(constants.CONFIG_FILE, str)
        assert isinstance(constants.OUTPUT_DIR, str)
        assert isinstance(constants.VERSION, str)

    def test_config_file_exists(self):
        """Test that config file exists."""
        assert _config_types_path().is_file()

    def test_config_file_valid_json(self):
        """Test that config file is valid JSON."""
        with _config_types_path().open(encoding="utf-8") as f:
            config = json.load(f)

        assert "regex" in config
        assert "ai-ner" in config
        assert isinstance(config["regex"], list)
        assert isinstance(config["ai-ner"], list)
