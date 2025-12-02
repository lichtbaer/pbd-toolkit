"""Configuration management for PII Toolkit."""

import csv
import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from gliner import GLiNER

import constants


@dataclass
class Config:
    """Configuration object for PII Toolkit.
    
    This class centralizes all configuration and dependencies,
    enabling dependency injection and better testability.
    """
    
    # CLI Arguments
    path: str
    use_regex: bool
    use_ner: bool
    verbose: bool
    outname: str | None = None
    whitelist_path: str | None = None
    stop_count: int | None = None
    
    # Dependencies
    logger: logging.Logger = field(default=None)
    csv_writer: Any = field(default=None)
    csv_file_handle: Any = field(default=None)
    
    # Processing configuration
    regex_pattern: re.Pattern | None = field(default=None)
    ner_model: GLiNER | None = field(default=None)
    ner_labels: list[str] = field(default_factory=list)
    ner_threshold: float = field(default=constants.NER_THRESHOLD)
    
    # Resource limits
    max_file_size_mb: float = 500.0
    max_processing_time_seconds: int = 300
    
    # Translation function
    _: Any = field(default=None)
    
    def __post_init__(self):
        """Initialize derived configuration after object creation."""
        if self._ is None:
            # Fallback if translation not set
            self._ = lambda x: x
    
    def validate_path(self) -> tuple[bool, str | None]:
        """Validate the search path.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not self.path:
            return False, self._("--path parameter cannot be empty")
        
        if not os.path.exists(self.path):
            return False, self._("Path does not exist: {}").format(self.path)
        
        if not os.path.isdir(self.path):
            return False, self._("Path is not a directory: {}").format(self.path)
        
        if not os.access(self.path, os.R_OK):
            return False, self._("Path is not readable: {}").format(self.path)
        
        return True, None
    
    def validate_file_path(self, file_path: str) -> tuple[bool, str | None]:
        """Validate file path and check for path traversal.
        
        Args:
            file_path: Path to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Resolve to absolute paths to prevent path traversal
            real_base = os.path.realpath(self.path)
            real_file = os.path.realpath(file_path)
            
            # Check if file is within base directory
            if not real_file.startswith(real_base + os.sep) and real_file != real_base:
                return False, "Path traversal attempt detected"
            
            # Check file size limit
            if os.path.isfile(file_path):
                file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
                if file_size_mb > self.max_file_size_mb:
                    return False, f"File too large: {file_size_mb:.2f} MB (max: {self.max_file_size_mb} MB)"
            
            return True, None
        except (OSError, ValueError) as e:
            return False, f"Path validation error: {str(e)}"
    
    @classmethod
    def from_args(cls, args: Any, logger: logging.Logger, csv_writer: Any, 
                  csv_file_handle: Any, translate_func: Any) -> "Config":
        """Create Config from command line arguments.
        
        Args:
            args: Parsed command line arguments
            logger: Logger instance
            csv_writer: CSV writer instance
            csv_file_handle: CSV file handle
            translate_func: Translation function
            
        Returns:
            Config instance
        """
        config = cls(
            path=args.path or "",
            use_regex=args.regex or False,
            use_ner=args.ner or False,
            verbose=args.verbose or False,
            outname=args.outname,
            whitelist_path=args.whitelist,
            stop_count=args.stop_count,
            logger=logger,
            csv_writer=csv_writer,
            csv_file_handle=csv_file_handle,
            _=translate_func
        )
        
        # Load regex pattern
        config._load_regex_pattern()
        
        # Load NER model if needed
        if config.use_ner:
            config._load_ner_model()
        
        return config
    
    def _load_regex_pattern(self) -> None:
        """Load and compile regex pattern from config file."""
        try:
            with open(constants.CONFIG_FILE) as f:
                config_data = json.load(f)
            
            regex_entries = config_data.get("regex", [])
            regex_supported = [r"{}".format(entry["expression"]) for entry in regex_entries]
            
            if regex_supported:
                rxstr_all = "(" + ")|(".join(regex_supported) + ")"
                self.regex_pattern = re.compile(rxstr_all)
        except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
            self.logger.warning(f"Failed to load regex pattern: {e}")
            self.regex_pattern = None
    
    def _load_ner_model(self) -> None:
        """Load NER model and labels.
        
        Loads the GLiNER model from HuggingFace and configures labels and threshold
        from config_types.json. Handles various error cases with specific error messages.
        """
        try:
            self.logger.info(self._("Loading NER model..."))
            self.ner_model = GLiNER.from_pretrained(constants.NER_MODEL_NAME)
            self.logger.info(self._("NER model loaded: {}").format(constants.NER_MODEL_NAME))
            
            with open(constants.CONFIG_FILE) as f:
                config_data = json.load(f)
            
            # Load NER labels
            ner_config = config_data.get("ai-ner", [])
            self.ner_labels = [c["term"] for c in ner_config]
            
            if not self.ner_labels:
                self.logger.warning(self._("No NER labels configured"))
            
            # Load threshold from config, fallback to constant
            settings = config_data.get("settings", {})
            self.ner_threshold = settings.get("ner_threshold", constants.NER_THRESHOLD)
            
            if self.verbose:
                self.logger.debug(f"NER threshold: {self.ner_threshold}")
                self.logger.debug(f"NER labels: {self.ner_labels}")
                
        except FileNotFoundError as e:
            error_msg = (
                self._("NER model not found. Please download it first:\n")
                + f"  hf download {constants.NER_MODEL_NAME}\n"
                + self._("Original error: {}").format(str(e))
            )
            self.logger.error(error_msg)
            raise RuntimeError(error_msg) from e
        except ImportError as e:
            error_msg = (
                self._("GLiNER library not installed. Install with:\n")
                + "  pip install gliner\n"
                + self._("Original error: {}").format(str(e))
            )
            self.logger.error(error_msg)
            raise RuntimeError(error_msg) from e
        except json.JSONDecodeError as e:
            error_msg = (
                self._("Failed to parse configuration file: {}").format(constants.CONFIG_FILE)
                + f"\n{self._('Original error: {}')}".format(str(e))
            )
            self.logger.error(error_msg)
            raise RuntimeError(error_msg) from e
        except Exception as e:
            error_msg = self._("Failed to load NER model: {}").format(str(e))
            self.logger.error(error_msg, exc_info=True)
            raise RuntimeError(error_msg) from e


def load_extended_config(config_file: str = constants.CONFIG_FILE) -> dict:
    """Load extended configuration from JSON file.
    
    Args:
        config_file: Path to configuration file
        
    Returns:
        Dictionary with configuration
    """
    try:
        with open(config_file) as f:
            config = json.load(f)
        
        # Set defaults for extended settings if not present
        if "settings" not in config:
            config["settings"] = {}
        
        settings = config["settings"]
        
        # Set defaults
        defaults = {
            "ner_threshold": constants.NER_THRESHOLD,
            "min_pdf_text_length": constants.MIN_PDF_TEXT_LENGTH,
            "max_file_size_mb": 500.0,
            "max_processing_time_seconds": 300,
            "supported_extensions": [".pdf", ".docx", ".html", ".txt"],
            "logging": {
                "level": "INFO",
                "format": "detailed"
            }
        }
        
        for key, value in defaults.items():
            if key not in settings:
                settings[key] = value
        
        return config
    except (FileNotFoundError, json.JSONDecodeError) as e:
        raise ValueError(f"Failed to load configuration: {e}")
