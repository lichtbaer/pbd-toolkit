import datetime
import json
import os
import re

import docx.opc.exceptions
import setup
from gliner import GLiNER
from tqdm import tqdm
import globals
from matches import PiiMatchContainer
import constants
from file_processors import (
    PdfProcessor,
    DocxProcessor,
    HtmlProcessor,
    TextProcessor,
)


""" Used to count how many files per extension have been found. This does *not* only count supported/qualified
    extensions but all of the ones contained in the root directory searched.
    Example: {".pdf": 42} indicates that there were 42 files with the extension ".pdf" in the root directory
    and its subdirectories. """
exts_found: dict[str, int] = {}

""" Used to hold information about special occurrences during analysis, such as files that could not be
    read due to an access violation or data corruption. The key contains the type of error, the value
    contains all files that produced that error.
    Example: { "file is password protected": ["a.pdf", "b.docx"]}"""
errors: dict[str, list[str]] = {}

""" Helper function for adding errors to the above dict without duplicating this branch all over the code. """
def add_error(msg: str, path: str) -> None:
    """Add an error message for a specific file path.
    
    Args:
        msg: Error message describing the type of error
        path: File path where the error occurred
    """
    if msg not in errors.keys():
        errors[msg] = [path]
    else:
        errors[msg].append(path)

# All regular expressions used for analysis.
with open(constants.CONFIG_FILE) as f:
    config = json.load(f)

regex = config["regex"]
regex_supported = []

for entry in regex:
    regex_supported.append(r"{}".format(entry["expression"]))

# concatenate all regex strings so that we can scan each document just once instead of once per regex
rxstr_all: str = "(" + ")|(".join(regex_supported) + ")"
regex_all: re.Pattern = re.compile(rxstr_all)

pmc: PiiMatchContainer = PiiMatchContainer()

# Used to list all entities for AI-based NER
ner_labels: list[str] = []

# TODO: move more stuff to globals
setup.setup()

if not globals.args.path:
    exit(globals._("--path parameter cannot be empty"))

if not os.path.exists(globals.args.path):
    exit(globals._("Path does not exist: {}").format(globals.args.path))

if not os.path.isdir(globals.args.path):
    exit(globals._("Path is not a directory: {}").format(globals.args.path))

if not os.access(globals.args.path, os.R_OK):
    exit(globals._("Path is not readable: {}").format(globals.args.path))

if not globals.args.ner and not globals.args.regex:
    exit(globals._("Regex- and/or NER-based analysis must be turned on."))

model: GLiNER | None = None
if globals.args.ner:
    model = GLiNER.from_pretrained(constants.NER_MODEL_NAME)
    ner_labels = [c["term"] for c in config["ai-ner"]]

if globals.args.whitelist and os.path.isfile(globals.args.whitelist):
    with open(globals.args.whitelist, "r") as file:
        pmc.whitelist = file.read().splitlines()

time_start: datetime.datetime = datetime.datetime.now()
time_end: datetime.datetime
time_diff: datetime.timedelta

globals.logger.info(globals._("Analysis"))
globals.logger.info("====================\n")
globals.logger.info(globals._("Analysis started at {}\n").format(time_start))

if globals.args.regex:
    globals.logger.info(globals._("Regex-based search is active."))
else:
    globals.logger.info(globals._("Regex-based search is *not* active."))

if globals.args.ner:
    globals.logger.info(globals._("AI-based search is active."))
    if globals.args.verbose:
        globals.logger.debug(f"NER Model: {constants.NER_MODEL_NAME}")
        globals.logger.debug(f"NER Threshold: {constants.NER_THRESHOLD}")
        globals.logger.debug(f"NER Labels: {ner_labels}")
else:
    globals.logger.info(globals._("AI-based search is *not* active."))

if globals.args.verbose:
    globals.logger.debug(f"Search path: {globals.args.path}")
    globals.logger.debug(f"Output directory: {constants.OUTPUT_DIR}")
    if globals.args.whitelist:
        globals.logger.debug(f"Whitelist file: {globals.args.whitelist}")
        globals.logger.debug(f"Whitelist entries: {len(pmc.whitelist)}")

globals.logger.info("\n")

# Number of files found during analysis
num_files_all: int = 0
# Number of files actually analyzed (supported file extension)
num_files_checked: int = 0


def get_file_processor(extension: str, file_path: str):
    """Get the appropriate file processor for a given file extension.
    
    Args:
        extension: File extension (e.g., '.pdf', '.docx')
        file_path: Full path to the file (needed for text file detection)
        
    Returns:
        Appropriate file processor instance or None if no processor available
    """
    processors = [
        PdfProcessor(),
        DocxProcessor(),
        HtmlProcessor(),
        TextProcessor(),
    ]
    
    for processor in processors:
        if hasattr(processor, 'can_process'):
            # TextProcessor needs file_path for mime type checking
            if isinstance(processor, TextProcessor):
                if processor.can_process(extension, file_path):
                    return processor
            elif processor.can_process(extension):
                return processor
    
    return None


def process_text(text: str, file_path: str, pmc: PiiMatchContainer, 
                 regex_all: re.Pattern | None, model: GLiNER | None, 
                 ner_labels: list[str], use_regex: bool, use_ner: bool) -> None:
    """Process text content with regex and/or NER-based PII detection.
    
    Args:
        text: Text content to analyze
        file_path: Path to the file containing the text
        pmc: PiiMatchContainer instance for storing matches
        regex_all: Compiled regex pattern for all regex types
        model: GLiNER model instance for NER (None if not used)
        ner_labels: List of NER labels to search for
        use_regex: Whether to use regex-based detection
        use_ner: Whether to use NER-based detection
    """
    if use_regex and regex_all:
        matches: re.Match | None = regex_all.search(text)
        pmc.add_matches_regex(matches, file_path)
    
    if use_ner and model:
        entities = model.predict_entities(text, ner_labels, threshold=constants.NER_THRESHOLD)
        pmc.add_matches_ner(entities, file_path)


""" MAIN PROGRAM LOOP """

# First pass: count total files for progress bar (if not using stop_count)
total_files_estimate = None
if not globals.args.stop_count:
    globals.logger.debug("Counting files for progress estimation...")
    total_files_estimate = sum(
        len(files) for _, _, files in os.walk(globals.args.path)
    )
    globals.logger.debug(f"Estimated total files: {total_files_estimate}")

# Initialize progress bar
progress_bar = None
if globals.args.verbose or not globals.args.stop_count:
    # Only show progress bar in verbose mode or for long-running operations
    progress_bar = tqdm(
        total=total_files_estimate if total_files_estimate else None,
        desc="Processing files",
        unit="file",
        disable=not globals.args.verbose and globals.args.stop_count is not None
    )

# walk all files and subdirs of the root path
for root, dirs, files in os.walk(globals.args.path):
    for filename in files:
        num_files_all += 1

        full_path: str = os.path.join(root, filename)
        ext: str = os.path.splitext(full_path)[1].lower()

        # keep count of how many files have been found per extension
        if ext not in exts_found.keys():
            exts_found[ext] = 1
        else:
            exts_found[ext] += 1

        # Log file processing in verbose mode
        if globals.args.verbose:
            try:
                file_size_mb = os.path.getsize(full_path) / (1024 * 1024)
                globals.logger.debug(f"Processing file {num_files_all}: {full_path} ({file_size_mb:.2f} MB)")
            except OSError:
                globals.logger.debug(f"Processing file {num_files_all}: {full_path} (size unknown)")

        # Get appropriate processor for this file type
        processor = get_file_processor(ext, full_path)
        
        if processor is not None:
            try:
                num_files_checked += 1
                
                # PDF processor yields text chunks, others return full text
                if isinstance(processor, PdfProcessor):
                    for text_chunk in processor.extract_text(full_path):
                        process_text(text_chunk, full_path, pmc, regex_all, model, 
                                   ner_labels, globals.args.regex, globals.args.ner)
                else:
                    text = processor.extract_text(full_path)
                    process_text(text, full_path, pmc, regex_all, model, 
                               ner_labels, globals.args.regex, globals.args.ner)
                
                if globals.args.verbose:
                    globals.logger.debug(f"Successfully processed: {full_path}")
                    
            except docx.opc.exceptions.PackageNotFoundError:
                error_msg = "DOCX Empty Or Protected"
                globals.logger.warning(f"{error_msg}: {full_path}")
                add_error(error_msg, full_path)
            except UnicodeDecodeError:
                error_msg = "Unicode Decode Error"
                globals.logger.warning(f"{error_msg}: {full_path}")
                add_error(error_msg, full_path)
            except PermissionError:
                error_msg = "Permission denied"
                globals.logger.warning(f"{error_msg}: {full_path}")
                add_error(error_msg, full_path)
            except FileNotFoundError:
                error_msg = "File not found"
                globals.logger.warning(f"{error_msg}: {full_path}")
                add_error(error_msg, full_path)
            except Exception as excpt:
                error_msg = f"Unexpected error: {type(excpt).__name__}: {str(excpt)}"
                globals.logger.error(f"{error_msg}: {full_path}", exc_info=globals.args.verbose)
                add_error(error_msg, full_path)
        else:
            if globals.args.verbose:
                globals.logger.debug(f"Skipping unsupported file type: {full_path}")

        # Update progress bar
        if progress_bar:
            progress_bar.update(1)
            progress_bar.set_postfix({
                'checked': num_files_checked,
                'errors': len(errors),
                'matches': len(pmc.pii_matches)
            })

        if globals.args.stop_count and num_files_all == globals.args.stop_count:
            break
    if globals.args.stop_count and num_files_all == globals.args.stop_count:
        break

# Close progress bar
if progress_bar:
    progress_bar.close()

time_end = datetime.datetime.now()
time_diff = time_end - time_start

""" Output all results. """
globals.logger.info(globals._("Statistics"))
globals.logger.info("----------\n")
globals.logger.info(globals._("The following file extensions have been found:"))
for k, v in sorted(exts_found.items(), key=lambda item: item[1], reverse=True):
    globals.logger.info("{:>10}: {:>10} Dateien".format(k, v))
globals.logger.info(globals._("TOTAL: {} files.\nQUALIFIED: {} files (supported file extension)\n\n").format(num_files_all, num_files_checked))

globals.logger.info(globals._("Findings"))
globals.logger.info("--------\n")
globals.logger.info(globals._("--> see *_findings.csv\n\n"))

globals.logger.info(globals._("Errors"))
globals.logger.info("------\n")
for k, v in errors.items():
    globals.logger.info("\t{}".format(k))
    for f in v:
        globals.logger.info("\t\t{}".format(f))

globals.logger.info("\n")
globals.logger.info(globals._("Analysis finished at {}").format(time_end))
globals.logger.info(globals._("Performance of analysis: {} analyzed files per second").format(round(num_files_checked / max(time_diff.seconds, 1), 2)))

# Close CSV file handle
if globals.csv_file_handle:
    globals.csv_file_handle.close()

