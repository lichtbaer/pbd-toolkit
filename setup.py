import argparse
import csv
import datetime
import gettext
import logging
import os
from pathlib import Path
from typing import Optional

import constants
from core.context import ApplicationContext
from core.config_loader import ConfigLoader
from output.writers import create_output_writer, OutputWriter

""" Setup language handling by referring to the environment variable LANGUAGE and loading the corresponding
    locales file. """
def __setup_lang() -> gettext.NullTranslations:
    """Initialize internationalization based on LANGUAGE environment variable.
    
    Returns:
        Translation object
    """
    lstr: str = os.environ.get("LANGUAGE")
    lenv: str = lstr if lstr and lstr in ["de", "en"] else "de"

    lang = gettext.translation("base", localedir="locales", languages=[lenv])
    lang.install()
    return lang

""" Setup CLI argument parsing. """
def __setup_args(translate_func: gettext.NullTranslations) -> argparse.Namespace:
    """Parse command line arguments.
    
    Args:
        translate_func: Translation function for help texts
    
    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        prog=translate_func("HBDI PII Toolkit"),
        description=translate_func("Scan directories for personally identifiable information"),
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Version
    parser.add_argument("--version", "-V", action="version", version="%(prog)s 1.0.0")
    
    # Required arguments
    parser.add_argument("--path", action="store", required=True, 
                       help=translate_func("Root directory under which to recursively search for PII"))
    
    # Analysis methods (at least one required, validated later)
    parser.add_argument("--regex", action="store_true", 
                       help=translate_func("Use regular expressions for analysis"))
    parser.add_argument("--ner", action="store_true", 
                       help=translate_func("Use AI-based Named Entity Recognition for analysis (GLiNER)"))
    
    # Additional NER engines
    parser.add_argument("--spacy-ner", action="store_true",
                       help=translate_func("Use spaCy NER models for detection"))
    parser.add_argument("--spacy-model", default="de_core_news_lg",
                       choices=["de_core_news_sm", "de_core_news_md", "de_core_news_lg"],
                       help=translate_func("spaCy model to use (default: de_core_news_lg)"))
    
    # LLM engines
    parser.add_argument("--ollama", action="store_true",
                       help=translate_func("Use Ollama LLM for detection"))
    parser.add_argument("--ollama-url", default="http://localhost:11434",
                       help=translate_func("Ollama API base URL (default: http://localhost:11434)"))
    parser.add_argument("--ollama-model", default="llama3.2",
                       help=translate_func("Ollama model to use (default: llama3.2)"))
    
    parser.add_argument("--openai-compatible", action="store_true",
                       help=translate_func("Use OpenAI-compatible API for detection"))
    parser.add_argument("--openai-api-base", default="https://api.openai.com/v1",
                       help=translate_func("OpenAI-compatible API base URL"))
    parser.add_argument("--openai-api-key",
                       help=translate_func("OpenAI API key (or set OPENAI_API_KEY env var)"))
    parser.add_argument("--openai-model", default="gpt-3.5-turbo",
                       help=translate_func("OpenAI model to use (default: gpt-3.5-turbo)"))
    
    # Optional arguments
    parser.add_argument("--outname", action="store", 
                       help=translate_func("Optional parameter; string which to include in the file name of all output files"))
    parser.add_argument("--whitelist", action="store", 
                       help=translate_func("Optional parameter; relative path to a text file containing one string per line. These strings will be matched against potential findings to exclude them from the output."))
    parser.add_argument("--stop-count", action="store", type=int, 
                       help=translate_func("Optional parameter; stop analysis after N files"))
    parser.add_argument("--output-dir", action="store", default="./output/",
                       help=translate_func("Directory for output files (default: ./output/)"))
    parser.add_argument("--format", choices=["csv", "json", "xlsx"], default="csv",
                       help=translate_func("Output format for findings (default: csv)"))
    parser.add_argument("--summary-format", choices=["human", "json"], default="human",
                       help=translate_func("Format for summary output (default: human). Use 'json' for machine-readable output."))
    parser.add_argument("--no-header", action="store_true",
                       help=translate_func("Don't include header row in CSV output (for backward compatibility)"))
    
    # Output options
    parser.add_argument("--verbose", "-v", action="store_true", 
                       help=translate_func("Enable verbose output with detailed logging"))
    parser.add_argument("--quiet", "-q", action="store_true",
                       help=translate_func("Suppress all output except errors"))
    
    parser.add_argument("--config", type=Path,
                       help=translate_func("Path to configuration file (YAML or JSON). CLI arguments override config file values."))
    
    args = parser.parse_args()
    
    # Load config file if provided
    if args.config:
        try:
            config_data = ConfigLoader.load_config(args.config)
            args = ConfigLoader.merge_with_args(config_data, args)
        except ValueError as e:
            parser.error(f"Configuration file error: {e}")
    
    return args

""" Setup logging.

    Logs are written to the output/ directory with the same name prefix as the findings file.
    Also outputs to console if verbose mode is enabled. """
def __setup_logger(args: Optional[argparse.Namespace], outslug: str = "") -> logging.Logger:
    """Setup logging.
    
    Args:
        args: Parsed command line arguments
        outslug: Slug for log file name
    
    Returns:
        Logger instance
    """
    # Determine log level based on verbose and quiet flags
    if args and args.quiet:
        log_level = logging.ERROR  # Only errors in quiet mode
    elif args and args.verbose:
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO
    
    # Create formatter with timestamp, level, and message
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Use constants.OUTPUT_DIR which is set in setup() before this is called
    # Ensure output directory ends with separator
    output_dir = constants.OUTPUT_DIR
    if not output_dir.endswith(os.sep):
        output_dir += os.sep
    
    # File handler for log file
    file_handler = logging.FileHandler(
        output_dir + outslug + "_log.txt",
        encoding="utf-8"
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    
    # Console handler for verbose output
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    
    # Configure root logger
    logger = logging.getLogger(__package__)
    logger.setLevel(log_level)
    logger.addHandler(file_handler)
    
    # Add console handler in verbose mode, or if not in quiet mode
    if args:
        if args.verbose:
            logger.addHandler(console_handler)
        elif not args.quiet:
            # In normal mode, show INFO and above
            console_handler.setLevel(logging.INFO)
            logger.addHandler(console_handler)
    
    return logger

""" Run all setup routines.

    Returns:
        Tuple of (args, logger, translate_func, output_writer, output_file_path)
    """
def __check_telemetry_settings() -> None:
    """Check and configure telemetry settings for privacy.
    
    Disables telemetry in dependencies to ensure privacy compliance.
    This function sets environment variables that disable telemetry
    in HuggingFace Hub, PyTorch, and other dependencies.
    """
    # Disable HuggingFace telemetry
    os.environ.setdefault('HF_HUB_DISABLE_TELEMETRY', '1')
    
    # Disable PyTorch telemetry (if PyTorch is used)
    os.environ.setdefault('TORCH_DISABLE_TELEMETRY', '1')
    
    # Note: tqdm telemetry is disabled by default in recent versions
    # For additional privacy, users can set TQDM_DISABLE_TELEMETRY=1

def setup() -> tuple[argparse.Namespace, logging.Logger, gettext.NullTranslations, Optional[OutputWriter], str]:
    """Setup application: parse arguments, setup logging, create output writer.
    
    Returns:
        Tuple of (args, logger, translate_func, output_writer, output_file_path)
    """
    # Disable telemetry in dependencies for privacy
    __check_telemetry_settings()
    
    translate_func = __setup_lang()
    args = __setup_args(translate_func)

    # construct name for output files. Default is date/time, optionally with the value from args.outname
    outslug: str = datetime.datetime.now().strftime("%Y-%m-%d %H-%M-%S")

    if args.outname is not None:
        outslug += " " + args.outname

    # Get output directory from args or use default
    output_dir = args.output_dir if args and hasattr(args, 'output_dir') else constants.OUTPUT_DIR
    # Ensure output directory ends with separator
    if not output_dir.endswith(os.sep):
        output_dir += os.sep
    
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Update constants.OUTPUT_DIR for use in other modules
    constants.OUTPUT_DIR = output_dir
    
    # Get output format from args
    output_format = args.format if args and hasattr(args, 'format') else "csv"
    
    # Determine file extension and create output file path
    extension_map = {"csv": ".csv", "json": ".json", "xlsx": ".xlsx"}
    extension = extension_map.get(output_format, ".csv")
    output_file_path = output_dir + outslug + "_findings" + extension
    
    # Create output writer
    include_header = not (args and hasattr(args, 'no_header') and args.no_header)
    output_writer = create_output_writer(
        output_format, 
        output_file_path, 
        include_header=include_header
    )

    logger = __setup_logger(args, outslug=outslug)
    
    return (args, logger, translate_func, output_writer, output_file_path)


def create_config(args: argparse.Namespace, logger: logging.Logger,
                 csv_writer: Any, csv_file_handle: Any,
                 translate_func: gettext.NullTranslations) -> "config.Config":
    """Create Config object from setup.
    
    Args:
        args: Parsed command line arguments
        logger: Logger instance
        csv_writer: CSV writer instance
        csv_file_handle: CSV file handle
        translate_func: Translation function
    
    Returns:
        Config instance with all dependencies injected
    """
    from config import Config
    
    return Config.from_args(
        args=args,
        logger=logger,
        csv_writer=csv_writer,
        csv_file_handle=csv_file_handle,
        translate_func=translate_func
    )
