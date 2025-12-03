import argparse
import csv
import datetime
import gettext
import logging
import os

import globals
import constants
from output.writers import create_output_writer

""" Setup language handling by referring to the environment variable LANGUAGE and loading the corresponding
    locales file. """
def __setup_lang() -> None:
    """Initialize internationalization based on LANGUAGE environment variable."""
    lstr: str = os.environ.get("LANGUAGE")
    lenv: str = lstr if lstr and lstr in ["de", "en"] else "de"

    lang = gettext.translation("base", localedir="locales", languages=[lenv])
    lang.install()
    globals._ = lang.gettext

""" Setup CLI argument parsing. """
def __setup_args() -> None:
    """Parse command line arguments and store them in globals.args."""
    parser = argparse.ArgumentParser(
        prog=globals._("HBDI PII Toolkit"),
        description=globals._("Scan directories for personally identifiable information"),
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Version
    parser.add_argument("--version", "-V", action="version", version="%(prog)s 1.0.0")
    
    # Required arguments
    parser.add_argument("--path", action="store", required=True, 
                       help=globals._("Root directory under which to recursively search for PII"))
    
    # Analysis methods (at least one required, validated later)
    parser.add_argument("--regex", action="store_true", 
                       help=globals._("Use regular expressions for analysis"))
    parser.add_argument("--ner", action="store_true", 
                       help=globals._("Use AI-based Named Entity Recognition for analysis"))
    
    # Optional arguments
    parser.add_argument("--outname", action="store", 
                       help=globals._("Optional parameter; string which to include in the file name of all output files"))
    parser.add_argument("--whitelist", action="store", 
                       help=globals._("Optional parameter; relative path to a text file containing one string per line. These strings will be matched against potential findings to exclude them from the output."))
    parser.add_argument("--stop-count", action="store", type=int, 
                       help=globals._("Optional parameter; stop analysis after N files"))
    parser.add_argument("--output-dir", action="store", default="./output/",
                       help=globals._("Directory for output files (default: ./output/)"))
    parser.add_argument("--format", choices=["csv", "json", "xlsx"], default="csv",
                       help=globals._("Output format for findings (default: csv)"))
    parser.add_argument("--no-header", action="store_true",
                       help=globals._("Don't include header row in CSV output (for backward compatibility)"))
    
    # Output options
    parser.add_argument("--verbose", "-v", action="store_true", 
                       help=globals._("Enable verbose output with detailed logging"))
    parser.add_argument("--quiet", "-q", action="store_true",
                       help=globals._("Suppress all output except errors"))
    
    globals.args = parser.parse_args()

""" Setup logging.

    Logs are written to the output/ directory with the same name prefix as the findings file.
    Also outputs to console if verbose mode is enabled. """
def __setup_logger(outslug: str = "") -> None:
    # Determine log level based on verbose and quiet flags
    if globals.args and globals.args.quiet:
        log_level = logging.ERROR  # Only errors in quiet mode
    elif globals.args and globals.args.verbose:
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
    globals.logger = logging.getLogger(__package__)
    globals.logger.setLevel(log_level)
    globals.logger.addHandler(file_handler)
    
    # Add console handler in verbose mode, or if not in quiet mode
    if globals.args:
        if globals.args.verbose:
            globals.logger.addHandler(console_handler)
        elif not globals.args.quiet:
            # In normal mode, show INFO and above
            console_handler.setLevel(logging.INFO)
            globals.logger.addHandler(console_handler)

""" Run all setup routines.

    These are used to populate globally used variables, e. g. for handling of i18n or logging. """
def setup() -> None:
    __setup_lang()
    __setup_args()

    # construct name for output files. Default is date/time, optionally with the value from args.outname
    outslug: str = datetime.datetime.now().strftime("%Y-%m-%d %H-%M-%S")

    if globals.args.outname is not None:
        outslug += " " + globals.args.outname

    # Get output directory from args or use default
    output_dir = globals.args.output_dir if globals.args and hasattr(globals.args, 'output_dir') else constants.OUTPUT_DIR
    # Ensure output directory ends with separator
    if not output_dir.endswith(os.sep):
        output_dir += os.sep
    
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Update constants.OUTPUT_DIR for use in other modules
    constants.OUTPUT_DIR = output_dir
    
    # Get output format from args
    output_format = globals.args.format if globals.args and hasattr(globals.args, 'format') else "csv"
    globals.output_format = output_format
    
    # Determine file extension and create output file path
    extension_map = {"csv": ".csv", "json": ".json", "xlsx": ".xlsx"}
    extension = extension_map.get(output_format, ".csv")
    output_file_path = output_dir + outslug + "_findings" + extension
    globals.output_file_path = output_file_path
    
    # Create output writer
    include_header = not (globals.args and hasattr(globals.args, 'no_header') and globals.args.no_header)
    globals.output_writer = create_output_writer(
        output_format, 
        output_file_path, 
        include_header=include_header
    )
    
    # Backward compatibility: Keep csvwriter and csv_file_handle for CSV format
    if output_format == "csv":
        # For CSV, we need to maintain backward compatibility
        from output.writers import CsvWriter
        if isinstance(globals.output_writer, CsvWriter):
            globals.csvwriter = globals.output_writer.get_writer()
            globals.csv_file_handle = globals.output_writer.file_handle
        else:
            globals.csv_file_handle = None
            globals.csvwriter = None
    else:
        globals.csv_file_handle = None
        globals.csvwriter = None

    __setup_logger(outslug=outslug)


def create_config() -> "config.Config":
    """Create Config object from current setup.
    
    Returns:
        Config instance with all dependencies injected
    """
    from config import Config
    
    return Config.from_args(
        args=globals.args,
        logger=globals.logger,
        csv_writer=globals.csvwriter,
        csv_file_handle=globals.csv_file_handle,
        translate_func=globals._
    )
