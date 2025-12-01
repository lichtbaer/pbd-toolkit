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
    globals.args = parser.parse_args()

""" Setup logging.

    Logs are written to the output/ directory with the same name prefix as the findings file. """
def __setup_logger(outslug: str = "") -> None:
    globals.logger = logging.getLogger(__package__)
    logging.basicConfig(filename=constants.OUTPUT_DIR + outslug + "_log.txt", format="%(message)s", encoding="utf-8", level=logging.INFO)

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
