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

    # Typer defaults (used to decide whether a CLI value was explicitly provided).
    # If the CLI value equals the default, we allow the config file to override it.
    _TYPER_DEFAULTS: dict[str, Any] = {
        # Methods / engines
        "regex": False,
        "ner": False,
        "spacy_ner": False,
        "spacy_model": "de_core_news_lg",
        "ollama": False,
        "ollama_url": "http://localhost:11434",
        "ollama_model": "llama3.2",
        "openai_compatible": False,
        "openai_api_base": "https://api.openai.com/v1",
        "openai_model": "gpt-3.5-turbo",
        "multimodal": False,
        "multimodal_api_base": None,
        "multimodal_api_key": None,
        "multimodal_model": "gpt-4-vision-preview",
        "multimodal_timeout": 60,
        "pydantic_ai": False,
        "pydantic_ai_provider": "openai",
        "pydantic_ai_model": None,
        "pydantic_ai_api_key": None,
        "pydantic_ai_base_url": None,
        # File type detection
        "use_magic_detection": False,
        "magic_fallback": True,
        # Output / misc
        "outname": None,
        "whitelist": None,
        "stop_count": None,
        "output_dir": "./output/",
        "format": "csv",
        "summary_format": "human",
        # Performance / execution
        "mode": "balanced",
        "jobs": None,
        "no_header": False,
        "statistics_mode": False,
        "statistics_output": None,
        "verbose": False,
        "quiet": False,
    }

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
            # NOTE: `path` is currently a required positional CLI argument in Typer.
            # We still accept it in the mapping for completeness, but it will not
            # override an explicitly provided CLI path.
            "path": "path",
            # Methods / engines
            "regex": "regex",
            "ner": "ner",
            "spacy_ner": "spacy_ner",
            "spacy_model": "spacy_model",
            "ollama": "ollama",
            "ollama_url": "ollama_url",
            "ollama_model": "ollama_model",
            "openai_compatible": "openai_compatible",
            "openai_api_base": "openai_api_base",
            "openai_api_key": "openai_api_key",
            "openai_model": "openai_model",
            "multimodal": "multimodal",
            "multimodal_api_base": "multimodal_api_base",
            "multimodal_api_key": "multimodal_api_key",
            "multimodal_model": "multimodal_model",
            "multimodal_timeout": "multimodal_timeout",
            "pydantic_ai": "pydantic_ai",
            "pydantic_ai_provider": "pydantic_ai_provider",
            "pydantic_ai_model": "pydantic_ai_model",
            "pydantic_ai_api_key": "pydantic_ai_api_key",
            "pydantic_ai_base_url": "pydantic_ai_base_url",
            # File type detection
            "use_magic_detection": "use_magic_detection",
            "magic_fallback": "magic_fallback",
            # Output / misc
            "outname": "outname",
            "whitelist": "whitelist",
            "stop_count": "stop_count",
            "output_dir": "output_dir",
            "format": "format",
            "no_header": "no_header",
            "verbose": "verbose",
            "quiet": "quiet",
            "summary_format": "summary_format",
            # Performance / execution
            "mode": "mode",
            "jobs": "jobs",
            "statistics_mode": "statistics_mode",
            "statistics_output": "statistics_output",
        }

        def _cli_value_is_default(arg_name: str, cli_value: Any) -> bool:
            """Return True if cli_value equals the Typer default for arg_name."""
            if arg_name not in ConfigLoader._TYPER_DEFAULTS:
                return False
            return cli_value == ConfigLoader._TYPER_DEFAULTS[arg_name]

        # Only set values that are not already set via CLI (or still at default).
        for config_key, arg_name in config_mapping.items():
            if config_key in config:
                cli_value = getattr(args, arg_name, None)

                # Decide if the config should override:
                # - If the CLI value is None, config can set it.
                # - If the CLI value equals the Typer default, config can override it.
                can_override = cli_value is None or _cli_value_is_default(arg_name, cli_value)
                if not can_override:
                    continue

                value = config[config_key]

                # Convert boolean strings if needed
                if isinstance(value, str) and value.lower() in ["true", "false"]:
                    value = value.lower() == "true"

                setattr(args, arg_name, value)

        return args
