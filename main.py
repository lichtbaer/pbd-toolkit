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
from output.writers import OutputWriter
from file_processors import (
    BaseFileProcessor,
    FileProcessorRegistry,
    PdfProcessor,
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


# Use FileProcessorRegistry for automatic processor discovery
# All processors are automatically registered when file_processors module is imported
def get_file_processor(extension: str, file_path: str):
    """Get the appropriate file processor for a given file extension.
    
    Uses FileProcessorRegistry for automatic processor discovery.
    Processors are stateless and thread-safe for reading operations.
    
    Args:
        extension: File extension (e.g., '.pdf', '.docx')
        file_path: Full path to the file (needed for text file detection)
        
    Returns:
        Appropriate file processor instance or None if no processor available
    """
    return FileProcessorRegistry.get_processor(extension, file_path)


# Thread lock for thread-safe operations
_process_lock = threading.Lock()
# Separate lock for NER model calls (GLiNER may not be thread-safe)
_ner_lock = threading.Lock()

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
        start_time = time.time()
        try:
            # Serialize NER model calls to ensure thread-safety
            # GLiNER model may not be thread-safe, so we use a separate lock
            with _ner_lock:
                entities = config.ner_model.predict_entities(
                    text, config.ner_labels, threshold=config.ner_threshold
                )
            processing_time = time.time() - start_time
            
            # Update statistics
            with _process_lock:
                config.ner_stats.total_chunks_processed += 1
                config.ner_stats.total_processing_time += processing_time
                config.ner_stats.total_entities_found += len(entities) if entities else 0
                
                # Count entities by type
                if entities:
                    for entity in entities:
                        entity_type = entity.get("label", "unknown")
                        config.ner_stats.entities_by_type[entity_type] = \
                            config.ner_stats.entities_by_type.get(entity_type, 0) + 1
                
                pmc.add_matches_ner(entities, file_path)
        except RuntimeError as e:
            # GPU/Model-spezifische Fehler
            config.ner_stats.errors += 1
            config.logger.warning(f"NER processing error for {file_path}: {e}")
            add_error("NER processing error", file_path)
        except MemoryError as e:
            # Speicherprobleme
            config.ner_stats.errors += 1
            config.logger.error(f"Out of memory during NER processing: {file_path}")
            add_error("NER memory error", file_path)
        except Exception as e:
            # Unerwartete Fehler
            config.ner_stats.errors += 1
            config.logger.error(
                f"Unexpected NER error for {file_path}: {type(e).__name__}: {e}",
                exc_info=config.verbose
            )
            add_error(f"NER error: {type(e).__name__}", file_path)


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
        if progress_bar is not None:
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
if progress_bar is not None:
    progress_bar.close()

time_end = datetime.datetime.now()
time_diff = time_end - time_start

# Calculate performance metrics
time_seconds = max(time_diff.total_seconds(), 0.001)  # Avoid division by zero
files_per_second = round(num_files_checked / time_seconds, 2)
total_errors = sum(len(v) for v in errors.values())

""" Output all results. """
# Always log detailed information
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
config.logger.info(config._("Performance of analysis: {} analyzed files per second").format(files_per_second))

# Output NER statistics if NER was used
if config.use_ner and config.ner_stats.total_chunks_processed > 0:
    config.logger.info("\n" + config._("NER Statistics"))
    config.logger.info("------------")
    avg_time = (config.ner_stats.total_processing_time / 
                config.ner_stats.total_chunks_processed)
    config.logger.info(config._("Chunks processed: {}").format(config.ner_stats.total_chunks_processed))
    config.logger.info(config._("Entities found: {}").format(config.ner_stats.total_entities_found))
    config.logger.info(config._("Total NER processing time: {:.2f}s").format(config.ner_stats.total_processing_time))
    config.logger.info(config._("Average time per chunk: {:.3f}s").format(avg_time))
    if config.ner_stats.entities_by_type:
        config.logger.info(config._("Entities by type:"))
        for entity_type, count in sorted(config.ner_stats.entities_by_type.items(), 
                                         key=lambda x: x[1], reverse=True):
            config.logger.info(f"  {entity_type}: {count}")
    if config.ner_stats.errors > 0:
        config.logger.warning(config._("NER errors encountered: {}").format(config.ner_stats.errors))

# Prepare metadata for output writers
output_metadata = {
    "start_time": time_start.isoformat(),
    "end_time": time_end.isoformat(),
    "duration_seconds": time_diff.total_seconds(),
    "path": config.path,
    "methods": {
        "regex": config.use_regex,
        "ner": config.use_ner
    },
    "total_files": num_files_all,
    "analyzed_files": num_files_checked,
    "matches_found": len(pmc.pii_matches),
    "errors": total_errors,
    "statistics": {
        "files_scanned": num_files_all,
        "files_analyzed": num_files_checked,
        "matches_found": len(pmc.pii_matches),
        "errors": total_errors,
        "throughput_files_per_sec": files_per_second
    },
    "file_extensions": dict(sorted(exts_found.items(), key=lambda item: item[1], reverse=True)),
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
    print(f"{config._('Started:')}     {time_start.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{config._('Finished:')}    {time_end.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{config._('Duration:')}    {time_diff}")
    print()
    print(config._("Statistics:"))
    print(f"  {config._('Files scanned:')}      {num_files_all:,}")
    print(f"  {config._('Files analyzed:')}     {num_files_checked:,}")
    print(f"  {config._('Matches found:')}      {len(pmc.pii_matches):,}")
    print(f"  {config._('Errors:')}             {total_errors:,}")
    print()
    print(config._("Performance:"))
    print(f"  {config._('Throughput:')}         {files_per_second} {config._('files/sec')}")
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

