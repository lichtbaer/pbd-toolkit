import datetime
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

import docx.opc.exceptions
import setup
from tqdm import tqdm
from config import Config
from matches import PiiMatchContainer
import constants
from file_processors import (
    BaseFileProcessor,
    PdfProcessor,
    DocxProcessor,
    HtmlProcessor,
    TextProcessor,
    CsvProcessor,
    JsonProcessor,
    RtfProcessor,
    OdtProcessor,
    EmlProcessor,
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
_error_lock = threading.Lock()

def add_error(msg: str, path: str) -> None:
    """Add an error message for a specific file path.
    
    Thread-safe error tracking.
    
    Args:
        msg: Error message describing the type of error
        path: File path where the error occurred
    """
    with _error_lock:
        if msg not in errors:
            errors[msg] = [path]
        else:
            errors[msg].append(path)

# Setup and create configuration
setup.setup()
config: Config = setup.create_config()

# Validate configuration
is_valid, error_msg = config.validate_path()
if not is_valid:
    exit(error_msg)

if not config.use_ner and not config.use_regex:
    exit(config._("Regex- and/or NER-based analysis must be turned on."))

# Initialize PII match container
pmc: PiiMatchContainer = PiiMatchContainer()
pmc.set_csv_writer(config.csv_writer)

# Load whitelist if provided
if config.whitelist_path and os.path.isfile(config.whitelist_path):
    with open(config.whitelist_path, "r", encoding="utf-8") as file:
        pmc.whitelist = file.read().splitlines()
    # Pre-compile whitelist pattern for better performance
    pmc._compile_whitelist_pattern()

time_start: datetime.datetime = datetime.datetime.now()
time_end: datetime.datetime
time_diff: datetime.timedelta

config.logger.info(config._("Analysis"))
config.logger.info("====================\n")
config.logger.info(config._("Analysis started at {}\n").format(time_start))

if config.use_regex:
    config.logger.info(config._("Regex-based search is active."))
else:
    config.logger.info(config._("Regex-based search is *not* active."))

if config.use_ner:
    config.logger.info(config._("AI-based search is active."))
    if config.verbose:
        config.logger.debug(f"NER Model: {constants.NER_MODEL_NAME}")
        config.logger.debug(f"NER Threshold: {constants.NER_THRESHOLD}")
        config.logger.debug(f"NER Labels: {config.ner_labels}")
else:
    config.logger.info(config._("AI-based search is *not* active."))

if config.verbose:
    config.logger.debug(f"Search path: {config.path}")
    config.logger.debug(f"Output directory: {constants.OUTPUT_DIR}")
    if config.whitelist_path:
        config.logger.debug(f"Whitelist file: {config.whitelist_path}")
        config.logger.debug(f"Whitelist entries: {len(pmc.whitelist)}")

config.logger.info("\n")

# Number of files found during analysis
num_files_all: int = 0
# Number of files actually analyzed (supported file extension)
num_files_checked: int = 0


# Cache file processors to avoid creating new instances for each file
# Processors are stateless and can be safely reused
_file_processors_cache: dict[str, BaseFileProcessor] = {}
_file_processors_list = [
    PdfProcessor(),
    DocxProcessor(),
    HtmlProcessor(),
    TextProcessor(),
    CsvProcessor(),
    JsonProcessor(),
    RtfProcessor(),
    OdtProcessor(),
    EmlProcessor(),
]

def get_file_processor(extension: str, file_path: str):
    """Get the appropriate file processor for a given file extension.
    
    Uses cached processor instances to avoid repeated instantiation.
    Processors are stateless and thread-safe for reading operations.
    
    Args:
        extension: File extension (e.g., '.pdf', '.docx')
        file_path: Full path to the file (needed for text file detection)
        
    Returns:
        Appropriate file processor instance or None if no processor available
    """
    # For known extensions, use direct cache lookup
    if extension and extension in _file_processors_cache:
        return _file_processors_cache[extension]
    
    # Check each processor (TextProcessor needs file_path for mime type checking)
    for processor in _file_processors_list:
        if hasattr(processor, 'can_process'):
            # TextProcessor needs file_path for mime type checking
            if isinstance(processor, TextProcessor):
                if processor.can_process(extension, file_path):
                    # TextProcessor can't be cached by extension alone
                    return processor
            elif processor.can_process(extension):
                # Cache by extension for other processors
                _file_processors_cache[extension] = processor
                return processor
    
    return None


# Thread lock for thread-safe operations
_process_lock = threading.Lock()

def process_text(text: str, file_path: str, pmc: PiiMatchContainer, config: Config) -> None:
    """Process text content with regex and/or NER-based PII detection.
    
    Args:
        text: Text content to analyze
        file_path: Path to the file containing the text
        pmc: PiiMatchContainer instance for storing matches
        config: Configuration object with all settings
    """
    if config.use_regex and config.regex_pattern:
        # Use finditer to find ALL matches, not just the first one
        for match in config.regex_pattern.finditer(text):
            with _process_lock:
                pmc.add_matches_regex(match, file_path)
    
    if config.use_ner and config.ner_model:
        entities = config.ner_model.predict_entities(
            text, config.ner_labels, threshold=constants.NER_THRESHOLD
        )
        with _process_lock:
            pmc.add_matches_ner(entities, file_path)


""" MAIN PROGRAM LOOP """

# Skip file counting if stop_count is set (saves time)
# For large directories, counting can be slow, so we estimate dynamically
total_files_estimate = None
if not config.stop_count:
    # Only count files if verbose mode (for accurate progress)
    # Otherwise, use dynamic estimation during processing
    if config.verbose:
        config.logger.debug("Counting files for progress estimation...")
        total_files_estimate = sum(
            len(files) for _, _, files in os.walk(config.path)
        )
        config.logger.debug(f"Estimated total files: {total_files_estimate}")

# Initialize progress bar
progress_bar = None
if config.verbose or not config.stop_count:
    # Only show progress bar in verbose mode or for long-running operations
    progress_bar = tqdm(
        total=total_files_estimate if total_files_estimate else None,
        desc="Processing files",
        unit="file",
        disable=not config.verbose and config.stop_count is not None
    )

# walk all files and subdirs of the root path
for root, dirs, files in os.walk(config.path):
    for filename in files:
        num_files_all += 1

        full_path: str = os.path.join(root, filename)
        ext: str = os.path.splitext(full_path)[1].lower()

        # keep count of how many files have been found per extension
        # Thread-safe extension counting
        with _error_lock:  # Reuse lock for extension counting
            exts_found[ext] = exts_found.get(ext, 0) + 1

        # Validate file path (path traversal protection)
        is_valid, error_msg = config.validate_file_path(full_path)
        if not is_valid:
            if error_msg and "Path traversal" in error_msg:
                config.logger.warning(f"Security: {error_msg} - {full_path}")
                add_error(error_msg, full_path)
                continue
            elif error_msg and "too large" in error_msg:
                config.logger.warning(f"{error_msg} - {full_path}")
                add_error(error_msg, full_path)
                continue
        
        # Log file processing in verbose mode
        if config.verbose:
            try:
                file_size_mb = os.path.getsize(full_path) / (1024 * 1024)
                config.logger.debug(f"Processing file {num_files_all}: {full_path} ({file_size_mb:.2f} MB)")
            except OSError:
                config.logger.debug(f"Processing file {num_files_all}: {full_path} (size unknown)")

        # Get appropriate processor for this file type
        processor = get_file_processor(ext, full_path)
        
        if processor is not None:
            try:
                num_files_checked += 1
                
                # PDF processor yields text chunks, others return full text
                if isinstance(processor, PdfProcessor):
                    for text_chunk in processor.extract_text(full_path):
                        if text_chunk.strip():  # Only process non-empty chunks
                            process_text(text_chunk, full_path, pmc, config)
                else:
                    text = processor.extract_text(full_path)
                    if text.strip():  # Only process if there's actual text
                        process_text(text, full_path, pmc, config)
                
                if config.verbose:
                    config.logger.debug(f"Successfully processed: {full_path}")
                    
            except docx.opc.exceptions.PackageNotFoundError:
                error_msg = "DOCX Empty Or Protected"
                config.logger.warning(f"{error_msg}: {full_path}")
                add_error(error_msg, full_path)
            except UnicodeDecodeError:
                error_msg = "Unicode Decode Error"
                config.logger.warning(f"{error_msg}: {full_path}")
                add_error(error_msg, full_path)
            except PermissionError:
                error_msg = "Permission denied"
                config.logger.warning(f"{error_msg}: {full_path}")
                add_error(error_msg, full_path)
            except FileNotFoundError:
                error_msg = "File not found"
                config.logger.warning(f"{error_msg}: {full_path}")
                add_error(error_msg, full_path)
            except Exception as excpt:
                error_msg = f"Unexpected error: {type(excpt).__name__}: {str(excpt)}"
                config.logger.error(f"{error_msg}: {full_path}", exc_info=config.verbose)
                add_error(error_msg, full_path)
        else:
            if config.verbose:
                config.logger.debug(f"Skipping unsupported file type: {full_path}")

        # Update progress bar
        if progress_bar:
            progress_bar.update(1)
            progress_bar.set_postfix({
                'checked': num_files_checked,
                'errors': len(errors),
                'matches': len(pmc.pii_matches)
            })

        if config.stop_count and num_files_all == config.stop_count:
            break
    if config.stop_count and num_files_all == config.stop_count:
        break

# Close progress bar
if progress_bar:
    progress_bar.close()

time_end = datetime.datetime.now()
time_diff = time_end - time_start

""" Output all results. """
config.logger.info(config._("Statistics"))
config.logger.info("----------\n")
config.logger.info(config._("The following file extensions have been found:"))
for k, v in sorted(exts_found.items(), key=lambda item: item[1], reverse=True):
    config.logger.info("{:>10}: {:>10} Dateien".format(k, v))
config.logger.info(config._("TOTAL: {} files.\nQUALIFIED: {} files (supported file extension)\n\n").format(num_files_all, num_files_checked))

config.logger.info(config._("Findings"))
config.logger.info("--------\n")
config.logger.info(config._("--> see *_findings.csv\n\n"))

config.logger.info(config._("Errors"))
config.logger.info("------\n")
for k, v in errors.items():
    config.logger.info("\t{}".format(k))
    for f in v:
        config.logger.info("\t\t{}".format(f))

config.logger.info("\n")
config.logger.info(config._("Analysis finished at {}").format(time_end))
config.logger.info(config._("Performance of analysis: {} analyzed files per second").format(round(num_files_checked / max(time_diff.seconds, 1), 2)))

# Close CSV file handle
if config.csv_file_handle:
    config.csv_file_handle.close()

