"""Tests for configuration management."""

import os

from core import constants
from core.config import Config, ScanConfig, load_extended_config


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


class TestScopedSubConfigs:
    """Tests for the scoped sub-config objects (scan/engine/output/runtime)
    and the live top-level -> sub-config sync (see #77)."""

    def test_construction_populates_sub_configs(self):
        """Sub-configs reflect constructor kwargs immediately."""
        config = Config(path="/tmp/x", verbose=True, max_pending_futures=7)

        assert config.scan.path == "/tmp/x"
        assert config.scan.max_pending_futures == 7
        assert config.runtime.verbose is True

    def test_post_construction_assignment_is_live_synced(self):
        """Setting a mirrored top-level field after construction updates the
        owning sub-config immediately -- not just at __post_init__ time."""
        config = Config()

        config.verbose = True
        config.max_file_size_mb = 42.0
        config.exclude_patterns = ["*.bak"]
        config.use_magic_detection = True

        assert config.runtime.verbose is True
        assert config.scan.max_file_size_mb == 42.0
        assert config.scan.exclude_patterns == ["*.bak"]
        assert config.scan.use_magic_detection is True

    def test_bulk_attribute_load_stays_in_sync(self):
        """Simulates the config-file/profile loading pattern used by the CLI
        (``for key, value in file_data.items(): setattr(cfg, key, value)``) --
        every field lands in its sub-config without a manual resync call."""
        config = Config()
        file_data = {"max_pending_futures": 99, "verbose": True, "outname": "out.csv"}

        for key, value in file_data.items():
            if hasattr(config, key):
                setattr(config, key, value)

        assert config.scan.max_pending_futures == 99
        assert config.runtime.verbose is True
        assert config.output.outname == "out.csv"

    def test_runtime_config_holds_logger_and_verbose(self):
        from unittest.mock import Mock

        logger = Mock()
        config = Config(logger=logger, verbose=True)

        assert config.runtime.logger is logger
        assert config.runtime.verbose is True

    def test_scan_config_validate_path_standalone(self, temp_dir):
        """ScanConfig.validate_path works without a full Config -- this is
        what lets scan-scoped components validate without depending on the
        rest of Config."""
        scan_config = ScanConfig(path=temp_dir)
        is_valid, error_msg = scan_config.validate_path()
        assert is_valid is True
        assert error_msg is None

        missing = ScanConfig(path="/nonexistent/path/12345")
        is_valid, error_msg = missing.validate_path()
        assert is_valid is False
        assert "does not exist" in error_msg.lower()

    def test_scan_config_validate_path_uses_translate_func(self, temp_dir):
        translated = []

        def translate(msg: str) -> str:
            translated.append(msg)
            return f"[de] {msg}"

        scan_config = ScanConfig(path="")
        is_valid, error_msg = scan_config.validate_path(translate)

        assert is_valid is False
        assert error_msg.startswith("[de] ")
        assert translated  # translate() was actually invoked

    def test_scan_config_validate_file_path_standalone(self, temp_dir):
        scan_config = ScanConfig(path=temp_dir, max_file_size_mb=500.0)
        valid_file = os.path.join(temp_dir, "test.txt")

        is_valid, error_msg = scan_config.validate_file_path(valid_file)
        assert is_valid is True

        traversal_path = os.path.join(temp_dir, "..", "etc", "passwd")
        is_valid, error_msg = scan_config.validate_file_path(traversal_path)
        assert is_valid is False
        assert "Path traversal" in error_msg

    def test_config_validate_path_delegates_and_translates(self):
        """Config.validate_path still routes through Config._ for translated
        CLI output, even though the underlying logic now lives on ScanConfig."""
        calls = []

        def translate(msg: str) -> str:
            calls.append(msg)
            return msg

        config = Config(path="", _=translate)
        is_valid, error_msg = config.validate_path()

        assert is_valid is False
        assert calls  # Config's translate function was used, not skipped

    def test_replacing_sub_config_wholesale_can_be_resynced(self):
        """_sync_sub_configs() is kept as an explicit escape hatch for the one
        case __setattr__ can't handle: replacing a sub-config object outright."""
        config = Config(max_pending_futures=5)
        config.scan = ScanConfig()  # fresh, out of sync with top-level
        assert config.scan.max_pending_futures != 5

        config._sync_sub_configs()
        assert config.scan.max_pending_futures == 5


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
