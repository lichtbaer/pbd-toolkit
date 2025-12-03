import datetime
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

import docx.opc.exceptions
import setup
from tqdm import tqdm
from config import Config
from matches import PiiMatchContainer
import constants
import globals as g
from core.exceptions import ConfigurationError, ProcessingError, OutputError
from core.scanner import FileScanner, FileInfo
from core.processor import TextProcessor
from core.statistics import Statistics
from output.writers import OutputWriter
# File processor imports no longer needed in main.py
# They are now used in core.processor


# Error tracking (will be replaced by Scanner in future)
errors: dict[str, list[str]] = {}
_error_lock = threading.Lock()

def add_error(msg: str, path: str) -> None:
    """Add an error message for a specific file path.
    
    Thread-safe error tracking.
    
    Args:
        msg: Error message describing the type of error
        path: File path where the error occurred
    
    Note: This function is kept for backward compatibility during refactoring.
          Errors are now also tracked by FileScanner.
    """
    with _error_lock:
        if msg not in errors:
            errors[msg] = [path]
        else:
            errors[msg].append(path)

# Setup and create configuration
setup.setup()
try:
    config: Config = setup.create_config()
except RuntimeError as e:
    # NER model loading failed - exit with error message
    print(f"Configuration error: {e}", file=sys.stderr)
    sys.exit(constants.EXIT_CONFIGURATION_ERROR)
except Exception as e:
    # Other configuration errors
    print(f"Configuration error: {e}", file=sys.stderr)
    sys.exit(constants.EXIT_CONFIGURATION_ERROR)

# Validate configuration
is_valid, error_msg = config.validate_path()
if not is_valid:
    print(f"Invalid path: {error_msg}", file=sys.stderr)
    sys.exit(constants.EXIT_INVALID_ARGUMENTS)

if not config.use_ner and not config.use_regex:
    print(config._("Regex- and/or NER-based analysis must be turned on."), file=sys.stderr)
    sys.exit(constants.EXIT_INVALID_ARGUMENTS)

# Validate that NER model is loaded if NER is enabled
if config.use_ner and config.ner_model is None:
    print(config._("NER is enabled but model could not be loaded. Please check the error messages above."), file=sys.stderr)
    sys.exit(constants.EXIT_CONFIGURATION_ERROR)

# Initialize PII match container
pmc: PiiMatchContainer = PiiMatchContainer()
pmc.set_csv_writer(config.csv_writer)
# Set output format from globals
pmc.set_output_format(g.output_format if hasattr(g, 'output_format') else "csv")

# Get output writer from globals
output_writer: Optional[OutputWriter] = None
if hasattr(g, 'output_writer') and g.output_writer is not None:
    output_writer = g.output_writer

# Load whitelist if provided
if config.whitelist_path and os.path.isfile(config.whitelist_path):
    with open(config.whitelist_path, "r", encoding="utf-8") as file:
        pmc.whitelist = file.read().splitlines()
    # Pre-compile whitelist pattern for better performance
    pmc._compile_whitelist_pattern()

# Initialize statistics tracker
statistics = Statistics()
statistics.start()

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
        config.logger.debug(f"NER Threshold: {config.ner_threshold}")
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


# File processor selection is now handled in core.processor.TextProcessor


# Initialize text processor for PII detection
text_processor = TextProcessor(config, pmc, statistics=statistics)


""" MAIN PROGRAM LOOP """

# Initialize scanner
scanner = FileScanner(config)

# Define callback function for processing each file
def process_file(file_info: FileInfo) -> None:
    """Process a single file: extract text and detect PII.
    
    Args:
        file_info: FileInfo object with file path and metadata
    """
    text_processor.process_file(file_info, error_callback=add_error)

# Scan directory and process files
scan_result = scanner.scan(
    path=config.path,
    file_callback=process_file,
    stop_count=config.stop_count
)

# Update statistics from scan result
statistics.update_from_scan_result(
    total_files=scan_result.total_files_found,
    files_processed=scan_result.files_processed,
    extension_counts=scan_result.extension_counts,
    errors=scan_result.errors
)

# Merge scanner errors with existing errors (for backward compatibility)
for error_type, file_list in scan_result.errors.items():
    if error_type not in errors:
        errors[error_type] = []
    errors[error_type].extend(file_list)

# Update match count in statistics
statistics.matches_found = len(pmc.pii_matches)

# Stop timing
statistics.stop()

# Calculate total errors (for backward compatibility with errors dict)
total_errors = sum(len(v) for v in errors.values())
statistics.total_errors = total_errors

""" Output all results. """
# Always log detailed information
config.logger.info(config._("Statistics"))
config.logger.info("----------\n")
config.logger.info(config._("The following file extensions have been found:"))
for k, v in sorted(statistics.extension_counts.items(), key=lambda item: item[1], reverse=True):
    config.logger.info("{:>10}: {:>10} Dateien".format(k, v))
config.logger.info(config._("TOTAL: {} files.\nQUALIFIED: {} files (supported file extension)\n\n").format(statistics.total_files_found, statistics.files_processed))

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
config.logger.info(config._("Analysis finished at {}").format(statistics.end_time))
config.logger.info(config._("Performance of analysis: {} analyzed files per second").format(statistics.files_per_second))

# Output NER statistics if NER was used
if config.use_ner and statistics.ner_stats.total_chunks_processed > 0:
    config.logger.info("\n" + config._("NER Statistics"))
    config.logger.info("------------")
    config.logger.info(config._("Chunks processed: {}").format(statistics.ner_stats.total_chunks_processed))
    config.logger.info(config._("Entities found: {}").format(statistics.ner_stats.total_entities_found))
    config.logger.info(config._("Total NER processing time: {:.2f}s").format(statistics.ner_stats.total_processing_time))
    config.logger.info(config._("Average time per chunk: {:.3f}s").format(statistics.avg_ner_time_per_chunk))
    if statistics.ner_stats.entities_by_type:
        config.logger.info(config._("Entities by type:"))
        for entity_type, count in sorted(statistics.ner_stats.entities_by_type.items(), 
                                         key=lambda x: x[1], reverse=True):
            config.logger.info(f"  {entity_type}: {count}")
    if statistics.ner_stats.errors > 0:
        config.logger.warning(config._("NER errors encountered: {}").format(statistics.ner_stats.errors))

# Prepare metadata for output writers
output_metadata = {
    "start_time": statistics.start_time.isoformat() if statistics.start_time else None,
    "end_time": statistics.end_time.isoformat() if statistics.end_time else None,
    "duration_seconds": statistics.duration_seconds,
    "path": config.path,
    "methods": {
        "regex": config.use_regex,
        "ner": config.use_ner
    },
    "total_files": statistics.total_files_found,
    "analyzed_files": statistics.files_processed,
    "matches_found": statistics.matches_found,
    "errors": statistics.total_errors,
    "statistics": statistics.get_summary_dict(),
    "file_extensions": dict(sorted(statistics.extension_counts.items(), key=lambda item: item[1], reverse=True)),
    "errors": [
        {
            "type": error_type,
            "files": file_list
        }
        for error_type, file_list in errors.items()
    ]
}

# Write output using writer
# For CSV: matches are already written during processing (streaming)
# For JSON/XLSX: we need to write all matches at the end
if output_writer:
    # For non-streaming formats (JSON, XLSX), write all matches now
    if not output_writer.supports_streaming:
        # Write all matches that were collected during processing
        for pm in pmc.pii_matches:
            output_writer.write_match(pm)
    
    # Finalize output (writes file for JSON/XLSX, closes handle for CSV)
    try:
        output_writer.finalize(metadata=output_metadata)
    except OutputError as e:
        config.logger.error(f"Failed to write output: {e}")
        sys.exit(constants.EXIT_GENERAL_ERROR)
else:
    # Fallback: Close CSV file handle if it exists
    if config.csv_file_handle:
        config.csv_file_handle.close()

# Show summary to console (unless in quiet mode)
if not (g.args and hasattr(g.args, 'quiet') and g.args.quiet):
    print("\n" + "=" * 50)
    print(config._("Analysis Summary"))
    print("=" * 50)
    if statistics.start_time:
        print(f"{config._('Started:')}     {statistics.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    if statistics.end_time:
        print(f"{config._('Finished:')}    {statistics.end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{config._('Duration:')}    {statistics.duration}")
    print()
    print(config._("Statistics:"))
    print(f"  {config._('Files scanned:')}      {statistics.total_files_found:,}")
    print(f"  {config._('Files analyzed:')}     {statistics.files_processed:,}")
    print(f"  {config._('Matches found:')}      {statistics.matches_found:,}")
    print(f"  {config._('Errors:')}             {statistics.total_errors:,}")
    print()
    print(config._("Performance:"))
    print(f"  {config._('Throughput:')}         {statistics.files_per_second} {config._('files/sec')}")
    print()
    if errors:
        print(config._("Errors Summary:"))
        for k, v in errors.items():
            print(f"  {k}: {len(v)} {config._('files')}")
        print()
    
    # Get output file name
    if hasattr(g, 'output_file_path') and g.output_file_path:
        output_file = g.output_file_path
    elif config.csv_file_handle:
        # Fallback: get filename from file handle for CSV
        output_file = config.csv_file_handle.name
    else:
        # Last resort fallback
        output_format = g.output_format if hasattr(g, 'output_format') else "csv"
        output_file = constants.OUTPUT_DIR + "_findings." + output_format
    
    print(f"{config._('Output file:')} {output_file}")
    print(f"{config._('Output directory:')} {constants.OUTPUT_DIR}")
    print("=" * 50 + "\n")

# Exit with success code
sys.exit(constants.EXIT_SUCCESS)

