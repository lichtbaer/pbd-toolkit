"""Tests for ConfigLoader."""

import argparse
import json
from pathlib import Path

import pytest

from core.config_loader import ConfigLoader


class TestConfigLoaderLoadConfig:
    """Tests for ConfigLoader.load_config()."""

    def test_load_config_json(self, temp_dir):
        """Test loading valid JSON configuration."""
        config_path = Path(temp_dir) / "config.json"
        config_path.write_text('{"regex": true, "verbose": true}', encoding="utf-8")
        result = ConfigLoader.load_config(config_path)
        assert result["regex"] is True
        assert result["verbose"] is True

    def test_load_config_yaml(self, temp_dir):
        """Test loading valid YAML configuration."""
        config_path = Path(temp_dir) / "config.yaml"
        config_path.write_text("regex: true\nverbose: true\n", encoding="utf-8")
        result = ConfigLoader.load_config(config_path)
        assert result["regex"] is True
        assert result["verbose"] is True

    def test_load_config_yml_extension(self, temp_dir):
        """Test loading YAML file with .yml extension."""
        config_path = Path(temp_dir) / "config.yml"
        config_path.write_text("regex: false\n", encoding="utf-8")
        result = ConfigLoader.load_config(config_path)
        assert result["regex"] is False

    def test_load_config_file_not_found(self, temp_dir):
        """Test that ValueError is raised when file does not exist."""
        config_path = Path(temp_dir) / "nonexistent.json"
        with pytest.raises(ValueError) as exc_info:
            ConfigLoader.load_config(config_path)
        assert "Configuration file not found" in str(exc_info.value)
        assert "nonexistent" in str(exc_info.value)

    def test_load_config_unsupported_format(self, temp_dir):
        """Test that ValueError is raised for unsupported file format."""
        config_path = Path(temp_dir) / "config.xml"
        config_path.write_text("<config></config>", encoding="utf-8")
        with pytest.raises(ValueError) as exc_info:
            ConfigLoader.load_config(config_path)
        assert "Unsupported configuration file format" in str(exc_info.value)
        assert ".xml" in str(exc_info.value)
        assert "Supported formats" in str(exc_info.value)

    def test_load_config_invalid_json(self, temp_dir):
        """Test that ValueError is raised for invalid JSON."""
        config_path = Path(temp_dir) / "config.json"
        config_path.write_text("{ invalid json }", encoding="utf-8")
        with pytest.raises(ValueError) as exc_info:
            ConfigLoader.load_config(config_path)
        assert "Failed to parse configuration file" in str(exc_info.value)

    def test_load_config_invalid_yaml(self, temp_dir):
        """Test that ValueError is raised for invalid YAML."""
        config_path = Path(temp_dir) / "config.yaml"
        config_path.write_text("invalid: yaml: content: [", encoding="utf-8")
        with pytest.raises(ValueError) as exc_info:
            ConfigLoader.load_config(config_path)
        assert "Failed to parse configuration file" in str(exc_info.value)

    def test_load_config_empty_yaml_returns_empty_dict(self, temp_dir):
        """Test that empty YAML returns empty dict (yaml.safe_load returns None)."""
        config_path = Path(temp_dir) / "config.yaml"
        config_path.write_text("", encoding="utf-8")
        result = ConfigLoader.load_config(config_path)
        assert result == {}

    def test_load_config_empty_json_returns_empty_dict(self, temp_dir):
        """Test that empty JSON object returns empty dict."""
        config_path = Path(temp_dir) / "config.json"
        config_path.write_text("{}", encoding="utf-8")
        result = ConfigLoader.load_config(config_path)
        assert result == {}


class TestConfigLoaderMergeWithArgs:
    """Tests for ConfigLoader.merge_with_args()."""

    def test_merge_with_args_config_fills_defaults(self):
        """Test that config file values fill in CLI defaults."""
        config = {"regex": True, "verbose": True}
        args = argparse.Namespace(
            path="/test",
            regex=False,  # Typer default
            verbose=False,  # Typer default
            outname=None,
            whitelist=None,
        )
        result = ConfigLoader.merge_with_args(config, args)
        assert result.regex is True
        assert result.verbose is True

    def test_merge_with_args_cli_precedence(self):
        """Test that CLI values take precedence over config."""
        config = {"regex": False, "verbose": False}
        args = argparse.Namespace(
            path="/test",
            regex=True,  # Explicitly set by user
            verbose=True,  # Explicitly set by user
            outname=None,
            whitelist=None,
        )
        result = ConfigLoader.merge_with_args(config, args)
        assert result.regex is True
        assert result.verbose is True

    def test_merge_with_args_boolean_strings(self):
        """Test that boolean strings 'true'/'false' are converted."""
        config = {"regex": "true", "verbose": "false"}
        args = argparse.Namespace(
            path="/test",
            regex=False,  # Typer default
            verbose=False,  # Typer default
            outname=None,
            whitelist=None,
        )
        result = ConfigLoader.merge_with_args(config, args)
        assert result.regex is True
        assert result.verbose is False

    def test_merge_with_args_config_sets_none_values(self):
        """Test that config can set values when CLI has None."""
        config = {"outname": "output.csv", "format": "json"}
        args = argparse.Namespace(
            path="/test",
            regex=False,
            verbose=False,
            outname=None,
            whitelist=None,
            format="csv",
            output_dir="./output/",
        )
        result = ConfigLoader.merge_with_args(config, args)
        assert result.outname == "output.csv"
        # format was at default "csv", so config can override
        assert result.format == "json"

    def test_merge_with_args_partial_config(self):
        """Test merge with partial config (only some keys)."""
        config = {"regex": True}
        args = argparse.Namespace(
            path="/test",
            regex=False,
            verbose=False,
            outname=None,
            whitelist=None,
        )
        result = ConfigLoader.merge_with_args(config, args)
        assert result.regex is True
        assert result.verbose is False

    def test_merge_with_args_empty_config(self):
        """Test merge with empty config leaves args unchanged."""
        config = {}
        args = argparse.Namespace(
            path="/test",
            regex=False,
            verbose=False,
            outname=None,
            whitelist=None,
        )
        result = ConfigLoader.merge_with_args(config, args)
        assert result.regex is False
        assert result.verbose is False
