import argparse
import csv
import datetime
import gettext
import logging
import os

import globals
import constants

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
    parser = argparse.ArgumentParser(prog=globals._("HBDI PII Toolkit"))
    parser.add_argument("--path", action="store", help=globals._("Root directory under which to recursively search for PII"))
    parser.add_argument("--outname", action="store", help=globals._("Optional parameter; string which to include in the file name of all output files"))
    parser.add_argument("--whitelist", action="store", help=globals._("Optional parameter; relative path to a text file containing one string per line. These strings will be matched against potential findings to exclude them from the output."))
    parser.add_argument("--stop-count", action="store", type=int, help=globals._("Optional parameter; stop analysis after N files"))
    parser.add_argument("--regex", action="store_true", help=globals._("Use regular expressions for analysis"))
    parser.add_argument("--ner", action="store_true", help=globals._("Use AI-based Named Entity Recognition for analysis"))
    parser.add_argument("--verbose", "-v", action="store_true", help=globals._("Enable verbose output with detailed logging"))
    globals.args = parser.parse_args()

""" Setup logging.

    Logs are written to the output/ directory with the same name prefix as the findings file.
    Also outputs to console if verbose mode is enabled. """
def __setup_logger(outslug: str = "") -> None:
    # Determine log level based on verbose flag
    log_level = logging.DEBUG if globals.args and globals.args.verbose else logging.INFO
    
    # Create formatter with timestamp, level, and message
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # File handler for log file
    file_handler = logging.FileHandler(
        constants.OUTPUT_DIR + outslug + "_log.txt",
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
    
    # Only add console handler in verbose mode
    if globals.args and globals.args.verbose:
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

    # Ensure output directory exists
    os.makedirs(constants.OUTPUT_DIR, exist_ok=True)
    
    globals.csv_file_handle = open(constants.OUTPUT_DIR + outslug + "_findings.csv", "w", encoding="utf-8")
    globals.csvwriter = csv.writer(globals.csv_file_handle)

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
