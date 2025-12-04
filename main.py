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
from core.exceptions import ConfigurationError, ProcessingError, OutputError
from core.scanner import FileScanner, FileInfo
from core.processor import TextProcessor
from core.statistics import Statistics
from core.context import ApplicationContext
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

# Setup application
try:
    args, logger, translate_func, output_writer, output_file_path = setup.setup()
except Exception as e:
    print(f"Setup error: {e}", file=sys.stderr)
    sys.exit(constants.EXIT_CONFIGURATION_ERROR)

# Create configuration
try:
    # Get CSV writer and handle from output writer if CSV format
    csv_writer = None
    csv_file_handle = None
    if output_writer and hasattr(output_writer, 'get_writer'):
        from output.writers import CsvWriter
        if isinstance(output_writer, CsvWriter):
            csv_writer = output_writer.get_writer()
            csv_file_handle = output_writer.file_handle
    
    config: Config = setup.create_config(
        args=args,
        logger=logger,
        csv_writer=csv_writer,
        csv_file_handle=csv_file_handle,
        translate_func=translate_func
    )
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

# Check if at least one detection method is enabled
enabled_methods = [
    config.use_regex,
    config.use_ner,
    config.use_spacy_ner,
    config.use_ollama,
    config.use_openai_compatible,
    getattr(config, 'use_multimodal', False)
]
if not any(enabled_methods):
    print(translate_func("At least one detection method must be enabled (--regex, --ner, --spacy-ner, --ollama, --openai-compatible, or --multimodal)."), file=sys.stderr)
    sys.exit(constants.EXIT_INVALID_ARGUMENTS)

# Validate that GLiNER model is loaded if GLiNER is enabled
if config.use_ner and config.ner_model is None:
    print(translate_func("GLiNER NER is enabled but model could not be loaded. Please check the error messages above."), file=sys.stderr)
    sys.exit(constants.EXIT_CONFIGURATION_ERROR)

# Initialize components
pmc: PiiMatchContainer = PiiMatchContainer()
pmc.set_csv_writer(csv_writer)
pmc.set_output_format(args.format if hasattr(args, 'format') else "csv")

statistics = Statistics()
statistics.start()  # Start timing before processing

# Create application context
context = ApplicationContext.from_cli_args(
    args=args,
    config=config,
    logger=logger,
    statistics=statistics,
    match_container=pmc,
    output_writer=output_writer,
    translate_func=translate_func
)
context.output_file_path = output_file_path

# Load whitelist if provided
if context.config.whitelist_path and os.path.isfile(context.config.whitelist_path):
    with open(context.config.whitelist_path, "r", encoding="utf-8") as file:
        context.match_container.whitelist = file.read().splitlines()
    # Pre-compile whitelist pattern for better performance
    context.match_container._compile_whitelist_pattern()

context.logger.info(context._("Analysis"))
context.logger.info("====================\n")
context.logger.info(context._("Analysis started at {}\n").format(context.statistics.start_time))

if context.config.use_regex:
    context.logger.info(context._("Regex-based search is active."))
else:
    context.logger.info(context._("Regex-based search is *not* active."))

if context.config.use_ner:
    context.logger.info(context._("AI-based search is active."))
    if context.config.verbose:
        context.logger.debug(f"NER Model: {constants.NER_MODEL_NAME}")
        context.logger.debug(f"NER Threshold: {context.config.ner_threshold}")
        context.logger.debug(f"NER Labels: {context.config.ner_labels}")
else:
    context.logger.info(context._("AI-based search is *not* active."))

if context.config.verbose:
    context.logger.debug(f"Search path: {context.config.path}")
    context.logger.debug(f"Output directory: {constants.OUTPUT_DIR}")
    if context.config.whitelist_path:
        context.logger.debug(f"Whitelist file: {context.config.whitelist_path}")
        context.logger.debug(f"Whitelist entries: {len(pmc.whitelist)}")

context.logger.info("\n")

# Number of files found during analysis
num_files_all: int = 0
# Number of files actually analyzed (supported file extension)
num_files_checked: int = 0


# File processor selection is now handled in core.processor.TextProcessor


# Initialize text processor for PII detection
text_processor = TextProcessor(config, pmc, statistics=statistics)


""" MAIN PROGRAM LOOP """

# Initialize scanner and processor
scanner = FileScanner(context.config)
text_processor = TextProcessor(context.config, context.match_container, statistics=context.statistics)

# Define callback function for processing each file
def process_file(file_info: FileInfo) -> None:
    """Process a single file: extract text and detect PII.
    
    Args:
        file_info: FileInfo object with file path and metadata
    """
    text_processor.process_file(file_info, error_callback=add_error)

# Scan directory and process files
scan_result = scanner.scan(
    path=context.config.path,
    file_callback=process_file,
    stop_count=context.config.stop_count
)

# Update statistics from scan result
context.statistics.update_from_scan_result(
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
context.statistics.matches_found = len(context.match_container.pii_matches)

# Stop timing
context.statistics.stop()

# Calculate total errors (for backward compatibility with errors dict)
total_errors = sum(len(v) for v in errors.values())
context.statistics.total_errors = total_errors

""" Output all results. """
# Always log detailed information
context.logger.info(context._("Statistics"))
context.logger.info("----------\n")
context.logger.info(context._("The following file extensions have been found:"))
for k, v in sorted(context.statistics.extension_counts.items(), key=lambda item: item[1], reverse=True):
    context.logger.info("{:>10}: {:>10} Dateien".format(k, v))
context.logger.info(context._("TOTAL: {} files.\nQUALIFIED: {} files (supported file extension)\n\n").format(context.statistics.total_files_found, context.statistics.files_processed))

context.logger.info(context._("Findings"))
context.logger.info("--------\n")
context.logger.info(context._("--> see *_findings.csv\n\n"))

context.logger.info(context._("Errors"))
context.logger.info("------\n")
for k, v in errors.items():
    context.logger.info("\t{}".format(k))
    for f in v:
        context.logger.info("\t\t{}".format(f))

context.logger.info("\n")
context.logger.info(context._("Analysis finished at {}").format(context.statistics.end_time))
context.logger.info(context._("Performance of analysis: {} analyzed files per second").format(context.statistics.files_per_second))

# Output NER statistics if NER was used
if context.config.use_ner and context.statistics.ner_stats.total_chunks_processed > 0:
    context.logger.info("\n" + context._("NER Statistics"))
    context.logger.info("------------")
    context.logger.info(context._("Chunks processed: {}").format(context.statistics.ner_stats.total_chunks_processed))
    context.logger.info(context._("Entities found: {}").format(context.statistics.ner_stats.total_entities_found))
    context.logger.info(context._("Total NER processing time: {:.2f}s").format(context.statistics.ner_stats.total_processing_time))
    context.logger.info(context._("Average time per chunk: {:.3f}s").format(context.statistics.avg_ner_time_per_chunk))
    if context.statistics.ner_stats.entities_by_type:
        context.logger.info(context._("Entities by type:"))
        for entity_type, count in sorted(context.statistics.ner_stats.entities_by_type.items(), 
                                         key=lambda x: x[1], reverse=True):
            context.logger.info(f"  {entity_type}: {count}")
    if context.statistics.ner_stats.errors > 0:
        context.logger.warning(context._("NER errors encountered: {}").format(context.statistics.ner_stats.errors))

# Prepare metadata for output writers
output_metadata = {
    "start_time": context.statistics.start_time.isoformat() if context.statistics.start_time else None,
    "end_time": context.statistics.end_time.isoformat() if context.statistics.end_time else None,
    "duration_seconds": context.statistics.duration_seconds,
    "path": context.config.path,
    "methods": {
        "regex": context.config.use_regex,
        "ner": context.config.use_ner
    },
    "total_files": context.statistics.total_files_found,
    "analyzed_files": context.statistics.files_processed,
    "matches_found": context.statistics.matches_found,
    "errors": context.statistics.total_errors,
    "statistics": context.statistics.get_summary_dict(),
    "file_extensions": dict(sorted(context.statistics.extension_counts.items(), key=lambda item: item[1], reverse=True)),
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
if context.output_writer:
    # For non-streaming formats (JSON, XLSX), write all matches now
    if not context.output_writer.supports_streaming:
        # Write all matches that were collected during processing
        for pm in context.match_container.pii_matches:
            context.output_writer.write_match(pm)
    
    # Finalize output (writes file for JSON/XLSX, closes handle for CSV)
    try:
        context.output_writer.finalize(metadata=output_metadata)
    except OutputError as e:
        context.logger.error(f"Failed to write output: {e}")
        sys.exit(constants.EXIT_GENERAL_ERROR)
else:
    # Fallback: Close CSV file handle if it exists
    if context.csv_file_handle:
        context.csv_file_handle.close()

# Show summary to console (unless in quiet mode)
if not (args and hasattr(args, 'quiet') and args.quiet):
    summary_format = getattr(args, 'summary_format', 'human') if args else 'human'
    
    if summary_format == 'json':
        # Machine-readable JSON output
        import json
        summary_data = {
            "start_time": context.statistics.start_time.isoformat() if context.statistics.start_time else None,
            "end_time": context.statistics.end_time.isoformat() if context.statistics.end_time else None,
            "duration_seconds": context.statistics.duration_seconds,
            "statistics": {
                "files_scanned": context.statistics.total_files_found,
                "files_analyzed": context.statistics.files_processed,
                "matches_found": context.statistics.matches_found,
                "errors": context.statistics.total_errors,
                "throughput_files_per_sec": context.statistics.files_per_second
            },
            "output_file": context.output_file_path or (constants.OUTPUT_DIR + "_findings." + context.output_format),
            "output_directory": constants.OUTPUT_DIR,
            "errors_summary": {k: len(v) for k, v in errors.items()} if errors else {}
        }
        print(json.dumps(summary_data, indent=2))
    else:
        # Human-readable output
        print("\n" + "=" * 50)
        print(context._("Analysis Summary"))
        print("=" * 50)
        if context.statistics.start_time:
            print(f"{context._('Started:')}     {context.statistics.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        if context.statistics.end_time:
            print(f"{context._('Finished:')}    {context.statistics.end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{context._('Duration:')}    {context.statistics.duration}")
        print()
        print(context._("Statistics:"))
        print(f"  {context._('Files scanned:')}      {context.statistics.total_files_found:,}")
        print(f"  {context._('Files analyzed:')}     {context.statistics.files_processed:,}")
        print(f"  {context._('Matches found:')}      {context.statistics.matches_found:,}")
        print(f"  {context._('Errors:')}             {context.statistics.total_errors:,}")
        print()
        print(context._("Performance:"))
        print(f"  {context._('Throughput:')}         {context.statistics.files_per_second} {context._('files/sec')}")
        print()
        if errors:
            print(context._("Errors Summary:"))
            for k, v in errors.items():
                print(f"  {k}: {len(v)} {context._('files')}")
            print()
        
        # Get output file name
        output_file = context.output_file_path or (constants.OUTPUT_DIR + "_findings." + context.output_format)
        
        print(f"{context._('Output file:')} {output_file}")
        print(f"{context._('Output directory:')} {constants.OUTPUT_DIR}")
        print("=" * 50 + "\n")

# Exit with success code
sys.exit(constants.EXIT_SUCCESS)

