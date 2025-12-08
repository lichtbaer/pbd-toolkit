"""Tests for setup and configuration."""

import os


class TestSetup:
    """Tests for setup functionality."""

    def test_constants_exist(self):
        """Test that constants are properly defined."""
        import constants

        assert hasattr(constants, "MIN_PDF_TEXT_LENGTH")
        assert hasattr(constants, "NER_THRESHOLD")
        assert hasattr(constants, "NER_MODEL_NAME")
        assert hasattr(constants, "CONFIG_FILE")
        assert hasattr(constants, "OUTPUT_DIR")

        # Check types
        assert isinstance(constants.MIN_PDF_TEXT_LENGTH, int)
        assert isinstance(constants.NER_THRESHOLD, float)
        assert isinstance(constants.NER_MODEL_NAME, str)
        assert isinstance(constants.CONFIG_FILE, str)
        assert isinstance(constants.OUTPUT_DIR, str)

    def test_config_file_exists(self):
        """Test that config file exists."""
        import constants

        assert os.path.exists(constants.CONFIG_FILE)

    def test_config_file_valid_json(self):
        """Test that config file is valid JSON."""
        import json
        import constants

        with open(constants.CONFIG_FILE, "r") as f:
            config = json.load(f)

        assert "regex" in config
        assert "ai-ner" in config
        assert isinstance(config["regex"], list)
        assert isinstance(config["ai-ner"], list)
