import argparse
import csv
import datetime
import logging

import globals

def __setup_args() -> None:
    parser = argparse.ArgumentParser(prog=_("HBDI PII Toolkit"))
    parser.add_argument("--path", action="store", help=_("Root directory under which to recursively search for PII"))
    parser.add_argument("--outname", action="store", help=_("Optional parameter; string which to include in the file name of all output files"))
    parser.add_argument("--whitelist", action="store", help=_("Optional parameter; relative path to a text file containing one string per line. These strings will be matched against potential findings to exclude them from the output."))
    parser.add_argument("--stop-count", action="store", type=int, help=_("Optional parameter; stop analysis after N files"))
    parser.add_argument("--regex", action="store_true", help=_("Use regular expressions for analysis"))
    parser.add_argument("--ner", action="store_true", help=_("Use AI-based Named Entity Recognition for analysis"))
    globals.args = parser.parse_args()

def __setup_logger(outslug: str = "") -> None:
    globals.logger = logging.getLogger(__package__)
    logging.basicConfig(filename="./output/" + outslug + "_log.txt", format="%(message)s", encoding="utf-8", level=logging.INFO)

def setup() -> None:
    __setup_args()

    # construct name for output files. Default is date/time, optionally with the value from args.outname
    outslug: str = datetime.datetime.now().strftime("%Y-%m-%d %H-%M-%S")

    if globals.args.outname is not None:
        outslug += " " + globals.args.outname

    outf = open("./output/" + outslug + "_findings.csv", "w")
    globals.csvwriter = csv.writer(outf)

    __setup_logger(outslug=outslug)
