"""Tests for configuration management."""

import os
from config import Config, load_extended_config
import constants


class TestConfig:
    """Tests for Config class."""

    def test_config_creation(self):
        """Test creating a Config object."""
        from unittest.mock import Mock

        mock_args = Mock()
        mock_args.path = "/test/path"
        mock_args.regex = True
        mock_args.ner = False
        mock_args.verbose = False
        mock_args.outname = None
        mock_args.whitelist = None
        mock_args.stop_count = None

        mock_logger = Mock()
        mock_csv_writer = Mock()
        mock_csv_file = Mock()

        def mock_translate(x):
            return x

        config = Config.from_args(
            args=mock_args,
            logger=mock_logger,
            csv_writer=mock_csv_writer,
            csv_file_handle=mock_csv_file,
            translate_func=mock_translate,
        )

        assert config.path == "/test/path"
        assert config.use_regex is True
        assert config.use_ner is False
        assert config.verbose is False

    def test_validate_path_valid(self, temp_dir):
        """Test path validation with valid path."""
        from unittest.mock import Mock

        mock_args = Mock()
        mock_args.path = temp_dir
        mock_args.regex = True
        mock_args.ner = False
        mock_args.verbose = False
        mock_args.outname = None
        mock_args.whitelist = None
        mock_args.stop_count = None

        mock_logger = Mock()
        mock_csv_writer = Mock()
        mock_csv_file = Mock()

        def mock_translate(x):
            return x

        config = Config.from_args(
            args=mock_args,
            logger=mock_logger,
            csv_writer=mock_csv_writer,
            csv_file_handle=mock_csv_file,
            translate_func=mock_translate,
        )

        is_valid, error_msg = config.validate_path()
        assert is_valid is True
        assert error_msg is None

    def test_validate_path_nonexistent(self):
        """Test path validation with non-existent path."""
        from unittest.mock import Mock

        mock_args = Mock()
        mock_args.path = "/nonexistent/path/12345"
        mock_args.regex = True
        mock_args.ner = False
        mock_args.verbose = False
        mock_args.outname = None
        mock_args.whitelist = None
        mock_args.stop_count = None

        mock_logger = Mock()
        mock_csv_writer = Mock()
        mock_csv_file = Mock()

        def mock_translate(x):
            return x

        config = Config.from_args(
            args=mock_args,
            logger=mock_logger,
            csv_writer=mock_csv_writer,
            csv_file_handle=mock_csv_file,
            translate_func=mock_translate,
        )

        is_valid, error_msg = config.validate_path()
        assert is_valid is False
        assert error_msg is not None

    def test_validate_file_path_traversal(self, temp_dir):
        """Test path traversal protection."""
        from unittest.mock import Mock

        mock_args = Mock()
        mock_args.path = temp_dir
        mock_args.regex = True
        mock_args.ner = False
        mock_args.verbose = False
        mock_args.outname = None
        mock_args.whitelist = None
        mock_args.stop_count = None

        mock_logger = Mock()
        mock_csv_writer = Mock()
        mock_csv_file = Mock()

        def mock_translate(x):
            return x

        config = Config.from_args(
            args=mock_args,
            logger=mock_logger,
            csv_writer=mock_csv_writer,
            csv_file_handle=mock_csv_file,
            translate_func=mock_translate,
        )

        # Test valid path within base
        valid_file = os.path.join(temp_dir, "test.txt")
        is_valid, error_msg = config.validate_file_path(valid_file)
        assert is_valid is True

        # Test path traversal attempt
        traversal_path = os.path.join(temp_dir, "..", "etc", "passwd")
        is_valid, error_msg = config.validate_file_path(traversal_path)
        assert is_valid is False
        assert "Path traversal" in error_msg

    def test_validate_file_path_size_limit(self, temp_dir):
        """Test file size limit validation."""
        from unittest.mock import Mock

        mock_args = Mock()
        mock_args.path = temp_dir
        mock_args.regex = True
        mock_args.ner = False
        mock_args.verbose = False
        mock_args.outname = None
        mock_args.whitelist = None
        mock_args.stop_count = None

        mock_logger = Mock()
        mock_csv_writer = Mock()
        mock_csv_file = Mock()

        def mock_translate(x):
            return x

        config = Config.from_args(
            args=mock_args,
            logger=mock_logger,
            csv_writer=mock_csv_writer,
            csv_file_handle=mock_csv_file,
            translate_func=mock_translate,
        )

        # Set a very small size limit for testing
        config.max_file_size_mb = 0.001  # 1 KB

        # Create a small file (should pass)
        small_file = os.path.join(temp_dir, "small.txt")
        with open(small_file, "w") as f:
            f.write("test")

        is_valid, error_msg = config.validate_file_path(small_file)
        assert is_valid is True

        # Create a file larger than 1KB (should fail)
        large_file = os.path.join(temp_dir, "large.txt")
        with open(large_file, "w") as f:
            f.write("x" * 2000)  # 2000 bytes > 1KB

        is_valid, error_msg = config.validate_file_path(large_file)
        assert is_valid is False
        assert "too large" in error_msg.lower()

    def test_from_args_with_engine_flags(self):
        """Test Config.from_args with engine-specific arguments."""
        from unittest.mock import Mock

        mock_args = Mock()
        mock_args.path = "/test"
        mock_args.regex = False
        mock_args.ner = False
        mock_args.verbose = False
        mock_args.outname = None
        mock_args.whitelist = None
        mock_args.stop_count = None
        mock_args.spacy_model = "de_core_news_sm"
        mock_args.ollama_url = "http://localhost:11435"
        mock_args.ollama_model = "llama2"
        mock_args.openai_api_base = "https://api.example.com"
        mock_args.openai_api_key = "sk-xxx"
        mock_args.openai_model = "gpt-4"
        mock_args.use_magic_detection = True
        mock_args.magic_fallback = False

        mock_logger = Mock()
        mock_csv_writer = Mock()
        mock_csv_file = Mock()

        config = Config.from_args(
            args=mock_args,
            logger=mock_logger,
            csv_writer=mock_csv_writer,
            csv_file_handle=mock_csv_file,
            translate_func=lambda x: x,
        )

        assert config.spacy_model_name == "de_core_news_sm"
        assert config.ollama_base_url == "http://localhost:11435"
        assert config.ollama_model == "llama2"
        assert config.openai_api_base == "https://api.example.com"
        assert config.openai_api_key == "sk-xxx"
        assert config.openai_model == "gpt-4"
        assert config.use_magic_detection is True
        assert config.magic_detection_fallback is False


class TestExtendedConfig:
    """Tests for extended configuration loading."""

    def test_load_extended_config(self):
        """Test loading extended configuration."""
        config = load_extended_config(constants.CONFIG_FILE)

        assert "settings" in config
        assert "regex" in config
        assert "ai-ner" in config

        settings = config["settings"]
        assert "ner_threshold" in settings
        assert "min_pdf_text_length" in settings
        assert "max_file_size_mb" in settings
        assert "max_processing_time_seconds" in settings
        assert "supported_extensions" in settings
        assert "logging" in settings

    def test_load_extended_config_defaults(self):
        """Test that defaults are set if not present."""
        # This test assumes the config file has settings
        # If it doesn't, defaults should be added
        config = load_extended_config(constants.CONFIG_FILE)
        settings = config["settings"]

        # All required settings should be present
        assert "ner_threshold" in settings
        assert "min_pdf_text_length" in settings
        assert isinstance(settings["ner_threshold"], (int, float))
        assert isinstance(settings["min_pdf_text_length"], int)
