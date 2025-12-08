"""Configuration file loader for CLI arguments."""

import argparse
import json
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None


class ConfigLoader:
    """Loads configuration from YAML or JSON files."""

    @staticmethod
    def load_config(config_path: Path) -> dict[str, Any]:
        """Load configuration from file.

        Args:
            config_path: Path to configuration file (YAML or JSON)

        Returns:
            Dictionary with configuration values

        Raises:
            ValueError: If file format is not supported or file cannot be read
        """
        if not config_path.exists():
            raise ValueError(f"Configuration file not found: {config_path}")

        suffix = config_path.suffix.lower()

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                if suffix in [".yaml", ".yml"]:
                    if yaml is None:
                        raise ValueError(
                            "YAML support requires PyYAML. Install with: pip install pyyaml"
                        )
                    return yaml.safe_load(f) or {}
                elif suffix == ".json":
                    return json.load(f)
                else:
                    raise ValueError(
                        f"Unsupported configuration file format: {suffix}. "
                        "Supported formats: .json, .yaml, .yml"
                    )
        except (json.JSONDecodeError, yaml.YAMLError) as e:
            raise ValueError(f"Failed to parse configuration file: {e}") from e
        except Exception as e:
            raise ValueError(f"Failed to read configuration file: {e}") from e

    @staticmethod
    def merge_with_args(
        config: dict[str, Any], args: argparse.Namespace
    ) -> argparse.Namespace:
        """Merge configuration file values with CLI arguments.

        CLI arguments take precedence over config file values.

        Args:
            config: Configuration dictionary from file
            args: Parsed CLI arguments (argparse.Namespace)

        Returns:
            Modified args object with merged values
        """
        # Map config keys to argument names
        config_mapping = {
            "path": "path",
            "regex": "regex",
            "ner": "ner",
            "outname": "outname",
            "whitelist": "whitelist",
            "stop_count": "stop_count",
            "output_dir": "output_dir",
            "format": "format",
            "no_header": "no_header",
            "verbose": "verbose",
            "quiet": "quiet",
            "summary_format": "summary_format",
        }

        # Only set values that are not already set via CLI
        for config_key, arg_name in config_mapping.items():
            if config_key in config:
                # Check if CLI argument was provided (for flags, check if True)
                cli_value = getattr(args, arg_name, None)
                if arg_name in ["regex", "ner", "verbose", "quiet", "no_header"]:
                    # For boolean flags, only set from config if not explicitly set via CLI
                    if not cli_value:
                        value = config[config_key]
                        if isinstance(value, str) and value.lower() in [
                            "true",
                            "false",
                        ]:
                            value = value.lower() == "true"
                        setattr(args, arg_name, value)
                else:
                    # For other arguments, only set if not provided via CLI
                    if cli_value is None:
                        value = config[config_key]
                        # Convert boolean strings if needed
                        if isinstance(value, str) and value.lower() in [
                            "true",
                            "false",
                        ]:
                            value = value.lower() == "true"
                        setattr(args, arg_name, value)

        return args
