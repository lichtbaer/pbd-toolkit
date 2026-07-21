"""Tests for configuration management."""

import logging
import os
from unittest.mock import Mock

import pytest

from core import constants
from core.config import (
    Config,
    EngineConfig,
    OutputConfig,
    RuntimeConfig,
    ScanConfig,
    load_extended_config,
)


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


class TestSubConfigDelegation:
    """Tests for the scan/engine/output/runtime single-source-of-truth split (#77)."""

    @pytest.mark.parametrize(
        ("attr", "group", "value"),
        [
            ("max_file_size_mb", "scan", 42.0),
            ("exclude_patterns", "scan", ["*.bak"]),
            ("whitelist_path", "scan", "/tmp/whitelist.txt"),
            ("use_ner", "engine", True),
            ("ner_threshold", "engine", 0.9),
            ("ollama_model", "engine", "llama2"),
            ("outname", "output", "out.csv"),
            ("min_severity", "output", "high"),
            ("dedup_max_entries", "output", 123),
            ("verbose", "runtime", True),
        ],
    )
    def test_set_via_top_level_visible_via_subconfig(self, attr, group, value):
        """Setting `config.<attr>` must be immediately visible via `config.<group>.<attr>`."""
        config = Config()
        setattr(config, attr, value)
        assert getattr(getattr(config, group), attr) == value
        # And reading back through the top level returns the identical value.
        assert getattr(config, attr) == value

    @pytest.mark.parametrize(
        ("attr", "group", "value"),
        [
            ("max_pending_futures", "scan", 7),
            ("vector_threshold", "engine", 0.42),
            ("text_chunk_size", "output", 999),
            ("logger", "runtime", logging.getLogger("x")),
        ],
    )
    def test_set_via_subconfig_visible_via_top_level(self, attr, group, value):
        """Setting `config.<group>.<attr>` directly must be visible at the top level too."""
        config = Config()
        setattr(getattr(config, group), attr, value)
        assert getattr(config, attr) == value

    def test_no_duplicate_storage_construction_time_value_stays_live(self):
        """Regression test for the bug this ticket fixes: previously, syncing only
        happened once at construction, so a later mutation via one path silently
        went stale relative to the other. There must be exactly one value now.
        """
        config = Config(max_file_size_mb=10.0)
        assert config.scan.max_file_size_mb == 10.0

        config.scan.max_file_size_mb = 20.0
        assert config.max_file_size_mb == 20.0

        config.max_file_size_mb = 30.0
        assert config.scan.max_file_size_mb == 30.0

    def test_construct_from_prebuilt_subconfigs(self):
        """Config can be built directly from pre-built scoped sub-configs."""
        scan = ScanConfig(path="/data", max_file_size_mb=5.0)
        engine = EngineConfig(use_regex=True)
        output = OutputConfig(outname="report.csv")
        runtime = RuntimeConfig(verbose=True)

        config = Config(scan=scan, engine=engine, output=output, runtime=runtime)

        assert config.scan is scan
        assert config.engine is engine
        assert config.output is output
        assert config.runtime is runtime
        assert config.path == "/data"
        assert config.use_regex is True
        assert config.outname == "report.csv"
        assert config.verbose is True

    def test_mixing_subconfig_object_and_flattened_field_raises(self):
        """Passing both scan= and a flattened scan field is ambiguous and rejected."""
        with pytest.raises(TypeError, match="scan"):
            Config(scan=ScanConfig(), path="/data")

    def test_unknown_flattened_kwarg_raises(self):
        """An unrecognized flattened keyword isn't silently swallowed."""
        with pytest.raises(TypeError, match="unexpected keyword argument"):
            Config(not_a_real_field=123)

    def test_mock_spec_config_still_permits_delegated_fields(self):
        """Mock(spec=Config), used throughout the test suite, must still recognize
        every previously-flat field name as legitimate (regression guard for the
        dir(Config) visibility that the property-based delegation relies on).
        """
        mock = Mock(spec=Config)
        mock.max_file_size_mb = 1.0
        mock.exclude_patterns = []
        mock.logger = Mock()
        assert mock.max_file_size_mb == 1.0
        assert mock.exclude_patterns == []


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
