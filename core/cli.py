"""CLI interface using Typer for modern command-line argument parsing."""

import os
from pathlib import Path
from typing import Optional

import typer

# Import existing setup and processing logic
import cli_setup as setup
import constants
from config import Config
from matches import PiiMatchContainer
from core.doctor import run_doctor
from core.exceptions import OutputError
from core.scanner import FileScanner, FileInfo
from core.processor import TextProcessor
from core.statistics import Statistics
from core.statistics_aggregator import StatisticsAggregator
from core.context import ApplicationContext
from core.config_loader import ConfigLoader

# Create Typer app
app = typer.Typer(
    name="pii-toolkit",
    help="Scan directories for personally identifiable information",
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode="rich",
)


def _get_cli_version() -> str:
    """Best-effort version string for CLI output.

    Prefers installed package metadata; falls back to constants.VERSION for
    editable/dev runs where metadata may be unavailable.
    """
    try:
        from importlib.metadata import version  # type: ignore

        return version("pii-toolkit")
    except Exception:
        return getattr(constants, "VERSION", "unknown")


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"pii-toolkit {_get_cli_version()}")
        raise typer.Exit()


@app.callback()
def _main(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help="Show version and exit",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """Global CLI options."""


def _create_argparse_namespace_from_typer_args(**kwargs) -> object:
    """Create an argparse-like namespace object from Typer arguments.

    This adapter allows us to use existing setup functions that expect argparse.Namespace.

    Args:
        **kwargs: All Typer command arguments

    Returns:
        Object with attributes matching argparse.Namespace
    """

    class Args:
        """Simple namespace-like class for compatibility."""

        pass

    args = Args()
    for key, value in kwargs.items():
        # Convert typer argument names to argparse-style names
        # e.g., spacy_ner -> spacy_ner (same)
        # e.g., openai_compatible -> openai_compatible (same)
        setattr(args, key, value)

    return args


@app.command()
def scan(
    # Optional path (positional or flag). If neither is provided, it can come from --config.
    path: Optional[str] = typer.Argument(
        None, help="Root directory under which to recursively search for PII"
    ),
    path_opt: Optional[str] = typer.Option(
        None,
        "--path",
        help="Root directory under which to recursively search for PII (alternative to positional PATH)",
    ),
    # Analysis methods (at least one required, validated later)
    regex: bool = typer.Option(
        False, "--regex", help="Use regular expressions for analysis"
    ),
    ner: bool = typer.Option(
        False,
        "--ner",
        help="Use AI-based Named Entity Recognition for analysis (GLiNER)",
    ),
    # Additional NER engines
    spacy_ner: bool = typer.Option(
        False, "--spacy-ner", help="Use spaCy NER models for detection"
    ),
    spacy_model: str = typer.Option(
        "de_core_news_lg",
        "--spacy-model",
        help="spaCy model to use (default: de_core_news_lg)",
        case_sensitive=False,
    ),
    # LLM engines
    ollama: bool = typer.Option(False, "--ollama", help="Use Ollama LLM for detection"),
    ollama_url: str = typer.Option(
        "http://localhost:11434",
        "--ollama-url",
        help="Ollama API base URL (default: http://localhost:11434)",
    ),
    ollama_model: str = typer.Option(
        "llama3.2", "--ollama-model", help="Ollama model to use (default: llama3.2)"
    ),
    openai_compatible: bool = typer.Option(
        False, "--openai-compatible", help="Use OpenAI-compatible API for detection"
    ),
    openai_api_base: str = typer.Option(
        "https://api.openai.com/v1",
        "--openai-api-base",
        help="OpenAI-compatible API base URL",
    ),
    openai_api_key: Optional[str] = typer.Option(
        None, "--openai-api-key", help="OpenAI API key (or set OPENAI_API_KEY env var)"
    ),
    openai_model: str = typer.Option(
        "gpt-3.5-turbo",
        "--openai-model",
        help="OpenAI model to use (default: gpt-3.5-turbo)",
    ),
    # Multimodal image detection
    multimodal: bool = typer.Option(
        False, "--multimodal", help="Use multimodal models for image PII detection"
    ),
    multimodal_api_base: Optional[str] = typer.Option(
        None,
        "--multimodal-api-base",
        help="Multimodal API base URL (defaults to --openai-api-base)",
    ),
    multimodal_api_key: Optional[str] = typer.Option(
        None,
        "--multimodal-api-key",
        help="Multimodal API key (defaults to --openai-api-key or OPENAI_API_KEY)",
    ),
    multimodal_model: str = typer.Option(
        "gpt-4-vision-preview",
        "--multimodal-model",
        help="Multimodal model to use (default: gpt-4-vision-preview)",
    ),
    multimodal_timeout: int = typer.Option(
        60,
        "--multimodal-timeout",
        help="Multimodal API timeout in seconds (default: 60)",
    ),
    # PydanticAI unified engine
    pydantic_ai: bool = typer.Option(
        False,
        "--pydantic-ai",
        help="Use PydanticAI unified LLM engine (recommended, replaces --ollama, --openai-compatible, --multimodal)",
    ),
    pydantic_ai_provider: str = typer.Option(
        "openai",
        "--pydantic-ai-provider",
        help="LLM provider for PydanticAI (default: openai)",
        case_sensitive=False,
    ),
    pydantic_ai_model: Optional[str] = typer.Option(
        None,
        "--pydantic-ai-model",
        help="Model name for PydanticAI (auto-determined from provider if not specified)",
    ),
    pydantic_ai_api_key: Optional[str] = typer.Option(
        None,
        "--pydantic-ai-api-key",
        help="API key for PydanticAI (or use provider-specific env vars)",
    ),
    pydantic_ai_base_url: Optional[str] = typer.Option(
        None,
        "--pydantic-ai-base-url",
        help="Base URL for PydanticAI (for custom endpoints)",
    ),
    # File type detection
    use_magic_detection: bool = typer.Option(
        False,
        "--use-magic-detection",
        help="Enable file type detection using magic numbers (file headers)",
    ),
    magic_fallback: bool = typer.Option(
        True,
        "--magic-fallback/--no-magic-fallback",
        help="Use magic detection as fallback when extension doesn't match (default: True)",
    ),
    # Optional arguments
    outname: Optional[str] = typer.Option(
        None,
        "--outname",
        help="Optional parameter; string which to include in the file name of all output files",
    ),
    whitelist: Optional[str] = typer.Option(
        None,
        "--whitelist",
        help="Optional parameter; relative path to a text file containing one string per line. These strings will be matched against potential findings to exclude them from the output.",
    ),
    stop_count: Optional[int] = typer.Option(
        None, "--stop-count", help="Optional parameter; stop analysis after N files"
    ),
    output_dir: str = typer.Option(
        "./output/",
        "--output-dir",
        help="Directory for output files (default: ./output/)",
    ),
    format: str = typer.Option(
        "csv",
        "--format",
        help="Output format for findings (default: csv)",
        case_sensitive=False,
    ),
    summary_format: str = typer.Option(
        "human",
        "--summary-format",
        help="Format for summary output (default: human). Use 'json' for machine-readable output.",
        case_sensitive=False,
    ),
    mode: str = typer.Option(
        "balanced",
        "--mode",
        help="Execution mode: safe (low resource), balanced (default), fast (max throughput)",
        case_sensitive=False,
    ),
    jobs: Optional[int] = typer.Option(
        None,
        "--jobs",
        help="Number of parallel file workers (overrides --mode).",
    ),
    no_header: bool = typer.Option(
        False,
        "--no-header",
        help="Don't include header row in CSV output (for backward compatibility)",
    ),
    statistics_mode: bool = typer.Option(
        False,
        "--statistics-mode",
        help="Generate privacy-focused statistics output (aggregated by dimension and module, no PII data)",
    ),
    statistics_strict: bool = typer.Option(
        False,
        "--statistics-strict",
        help="Strict privacy statistics mode: do not keep file paths in memory (some file-unique metrics become null).",
    ),
    statistics_output: Optional[str] = typer.Option(
        None,
        "--statistics-output",
        help="Path for statistics JSON output file (default: auto-generated in output directory)",
    ),
    # Output options
    verbose: bool = typer.Option(
        False, "-v", "--verbose", help="Enable verbose output with detailed logging"
    ),
    quiet: bool = typer.Option(
        False, "-q", "--quiet", help="Suppress all output except errors"
    ),
    # Config file
    config: Optional[Path] = typer.Option(
        None,
        "--config",
        help="Path to configuration file (YAML or JSON). CLI arguments override config file values.",
    ),
) -> None:
    """Scan directory for PII using specified detection methods.

    At least one detection method must be enabled (--regex, --ner, --spacy-ner,
    --ollama, --openai-compatible, --multimodal, or --pydantic-ai).
    """
    # Disable telemetry in dependencies for privacy
    setup.__check_telemetry_settings()

    # Setup language handling
    translate_func = setup.__setup_lang()

    # Create argparse-like namespace for compatibility with existing code
    # Prefer --path over positional PATH (if both are provided).
    resolved_path = path_opt or path

    typer_args = {
        "path": resolved_path,
        "regex": regex,
        "ner": ner,
        "spacy_ner": spacy_ner,
        "spacy_model": spacy_model,
        "ollama": ollama,
        "ollama_url": ollama_url,
        "ollama_model": ollama_model,
        "openai_compatible": openai_compatible,
        "openai_api_base": openai_api_base,
        "openai_api_key": openai_api_key or os.environ.get("OPENAI_API_KEY"),
        "openai_model": openai_model,
        "multimodal": multimodal,
        "multimodal_api_base": multimodal_api_base,
        "multimodal_api_key": multimodal_api_key,
        "multimodal_model": multimodal_model,
        "multimodal_timeout": multimodal_timeout,
        "pydantic_ai": pydantic_ai,
        "pydantic_ai_provider": pydantic_ai_provider,
        "pydantic_ai_model": pydantic_ai_model,
        "pydantic_ai_api_key": pydantic_ai_api_key,
        "pydantic_ai_base_url": pydantic_ai_base_url,
        "use_magic_detection": use_magic_detection,
        "magic_fallback": magic_fallback,
        "outname": outname,
        "whitelist": whitelist,
        "stop_count": stop_count,
        "output_dir": output_dir,
        "format": format,
        "summary_format": summary_format,
        "mode": mode,
        "jobs": jobs,
        "no_header": no_header,
        "statistics_mode": statistics_mode,
        "statistics_strict": statistics_strict,
        "statistics_output": statistics_output,
        "verbose": verbose,
        "quiet": quiet,
        "config": config,
    }

    args = _create_argparse_namespace_from_typer_args(**typer_args)

    # Load config file if provided
    if config:
        try:
            config_data = ConfigLoader.load_config(config)
            args = ConfigLoader.merge_with_args(config_data, args)
        except ValueError as e:
            typer.echo(f"Configuration file error: {e}", err=True)
            raise typer.Exit(code=constants.EXIT_CONFIGURATION_ERROR)

    # Ensure a scan path exists (positional PATH, --path, or config file).
    if not getattr(args, "path", None):
        typer.echo(
            translate_func(
                "Missing scan path. Provide PATH as positional argument, via --path, or in the config file as 'path'."
            ),
            err=True,
        )
        raise typer.Exit(code=constants.EXIT_INVALID_ARGUMENTS)

    # Construct name for output files
    import datetime

    outslug: str = datetime.datetime.now().strftime("%Y-%m-%d %H-%M-%S")
    if args.outname is not None:
        outslug += " " + args.outname

    # Get output directory from args or use default
    output_dir = (
        args.output_dir
        if hasattr(args, "output_dir") and args.output_dir
        else constants.OUTPUT_DIR
    )
    # Ensure output directory ends with separator
    if not output_dir.endswith(os.sep):
        output_dir += os.sep

    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Get output format from args
    output_format = args.format if hasattr(args, "format") else "csv"

    # Determine file extension and create output file path
    extension_map = {"csv": ".csv", "json": ".json", "jsonl": ".jsonl", "xlsx": ".xlsx"}
    extension = extension_map.get(output_format, ".csv")
    output_file_path = output_dir + outslug + "_findings" + extension

    # Create output writer
    include_header = not (hasattr(args, "no_header") and args.no_header)
    from core.writers import create_output_writer

    output_writer = create_output_writer(
        output_format, output_file_path, include_header=include_header
    )

    # Setup logger
    logger = setup.__setup_logger(args, outslug=outslug, output_dir=output_dir)

    # Get CSV writer and handle from output writer if CSV format
    csv_writer = None
    csv_file_handle = None
    if output_writer and hasattr(output_writer, "get_writer"):
        from core.writers import CsvWriter

        if isinstance(output_writer, CsvWriter):
            csv_writer = output_writer.get_writer()
            csv_file_handle = output_writer.file_handle

    # Create configuration
    try:
        config_obj: Config = setup.create_config(
            args=args,
            logger=logger,
            csv_writer=csv_writer,
            csv_file_handle=csv_file_handle,
            translate_func=translate_func,
        )
    except RuntimeError as e:
        # NER model loading failed - exit with error message
        typer.echo(f"Configuration error: {e}", err=True)
        raise typer.Exit(code=constants.EXIT_CONFIGURATION_ERROR)
    except Exception as e:
        # Other configuration errors
        typer.echo(f"Configuration error: {e}", err=True)
        raise typer.Exit(code=constants.EXIT_CONFIGURATION_ERROR)

    # Validate configuration
    is_valid, error_msg = config_obj.validate_path()
    if not is_valid:
        typer.echo(f"Invalid path: {error_msg}", err=True)
        raise typer.Exit(code=constants.EXIT_INVALID_ARGUMENTS)

    # Check if at least one detection method is enabled
    enabled_methods = [
        config_obj.use_regex,
        config_obj.use_ner,
        config_obj.use_spacy_ner,
        config_obj.use_ollama,
        config_obj.use_openai_compatible,
        getattr(config_obj, "use_multimodal", False),
        getattr(config_obj, "use_pydantic_ai", False),
    ]
    if not any(enabled_methods):
        typer.echo(
            translate_func(
                "At least one detection method must be enabled (--regex, --ner, --spacy-ner, --ollama, --openai-compatible, --multimodal, or --pydantic-ai)."
            ),
            err=True,
        )
        raise typer.Exit(code=constants.EXIT_INVALID_ARGUMENTS)

    # Validate that GLiNER model is loaded if GLiNER is enabled
    if config_obj.use_ner and config_obj.ner_model is None:
        typer.echo(
            translate_func(
                "GLiNER NER is enabled but model could not be loaded. Please check the error messages above."
            ),
            err=True,
        )
        raise typer.Exit(code=constants.EXIT_CONFIGURATION_ERROR)

    # Initialize components
    pmc: PiiMatchContainer = PiiMatchContainer()
    pmc.set_csv_writer(csv_writer)
    pmc.set_output_format(args.format if hasattr(args, "format") else "csv")
    # Enable streaming writes for writers that support it (e.g. csv/jsonl/xlsx).
    pmc.set_output_writer(output_writer)

    statistics = Statistics()
    statistics.start()  # Start timing before processing

    # Initialize statistics aggregator if statistics mode is enabled
    statistics_aggregator = None
    if hasattr(args, "statistics_mode") and args.statistics_mode:
        statistics_aggregator = StatisticsAggregator(
            strict=bool(getattr(args, "statistics_strict", False))
        )

    # Create application context
    context = ApplicationContext.from_cli_args(
        args=args,
        config=config_obj,
        logger=logger,
        statistics=statistics,
        match_container=pmc,
        output_writer=output_writer,
        translate_func=translate_func,
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
    context.logger.info(
        context._("Analysis started at {}\n").format(context.statistics.start_time)
    )

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
        context.logger.debug(f"Output directory: {output_dir}")
        if context.config.whitelist_path:
            context.logger.debug(f"Whitelist file: {context.config.whitelist_path}")
            context.logger.debug(f"Whitelist entries: {len(pmc.whitelist)}")

    context.logger.info("\n")

    # Error tracking (for backward compatibility)
    errors: dict[str, list[str]] = {}
    import threading

    _error_lock = threading.Lock()

    def add_error(msg: str, path: str) -> None:
        """Add an error message for a specific file path.

        Thread-safe error tracking.
        """
        with _error_lock:
            if msg not in errors:
                errors[msg] = [path]
            else:
                errors[msg].append(path)

    # Initialize text processor for PII detection
    text_processor = TextProcessor(
        context.config, context.match_container, statistics=context.statistics
    )

    # Initialize scanner
    scanner = FileScanner(context.config)

    # Define callback function for processing each file
    mode_lower = (getattr(args, "mode", "balanced") or "balanced").lower()
    cpu_count = os.cpu_count() or 4
    if getattr(args, "jobs", None):
        worker_count = max(1, int(args.jobs))
    else:
        if mode_lower == "safe":
            worker_count = 1
        elif mode_lower == "fast":
            worker_count = min(32, max(2, cpu_count * 4))
        else:
            worker_count = max(1, cpu_count)

    # Keep aggregator thread-safe if used from workers
    _stats_lock = threading.Lock()

    def _process_file_impl(file_info: FileInfo) -> None:
        """Process a single file: extract text and detect PII."""
        text_processor.process_file(file_info, error_callback=add_error)
        # Track file for statistics aggregator
        if statistics_aggregator:
            with _stats_lock:
                statistics_aggregator.add_file_scanned(
                    file_info.path, was_analyzed=True
                )
                # Track which engines processed this file
                if context.config.use_regex:
                    statistics_aggregator.add_file_processed(file_info.path, "regex")
                if context.config.use_ner:
                    statistics_aggregator.add_file_processed(file_info.path, "gliner")
                if getattr(context.config, "use_spacy_ner", False):
                    statistics_aggregator.add_file_processed(file_info.path, "spacy-ner")
                if getattr(context.config, "use_pydantic_ai", False):
                    statistics_aggregator.add_file_processed(
                        file_info.path, "pydantic-ai"
                    )

    if worker_count <= 1:
        def process_file(file_info: FileInfo) -> None:
            _process_file_impl(file_info)
    else:
        import concurrent.futures

        executor = concurrent.futures.ThreadPoolExecutor(max_workers=worker_count)

        def process_file(file_info: FileInfo):
            return executor.submit(_process_file_impl, file_info)

    # Scan directory and process files
    try:
        scan_result = scanner.scan(
            path=context.config.path,
            file_callback=process_file,
            stop_count=context.config.stop_count,
        )
    finally:
        # Ensure worker threads are cleaned up even if scanning fails.
        if worker_count > 1:
            try:
                executor.shutdown(wait=True)
            except Exception:
                pass

    # Update statistics from scan result
    context.statistics.update_from_scan_result(
        total_files=scan_result.total_files_found,
        files_processed=scan_result.files_processed,
        extension_counts=scan_result.extension_counts,
        errors=scan_result.errors,
    )

    # Merge scanner errors with existing errors
    for error_type, file_list in scan_result.errors.items():
        if error_type not in errors:
            errors[error_type] = []
        errors[error_type].extend(file_list)

    # Update match count in statistics
    context.statistics.matches_found = len(context.match_container.pii_matches)

    # Aggregate matches for statistics mode
    if statistics_aggregator:
        for match in context.match_container.pii_matches:
            statistics_aggregator.add_match(match)

    # Stop timing
    context.statistics.stop()

    # Calculate total errors
    total_errors = sum(len(v) for v in errors.values())
    context.statistics.total_errors = total_errors

    # Output all results
    context.logger.info(context._("Statistics"))
    context.logger.info("----------\n")
    context.logger.info(context._("The following file extensions have been found:"))
    for k, v in sorted(
        context.statistics.extension_counts.items(),
        key=lambda item: item[1],
        reverse=True,
    ):
        context.logger.info("{:>10}: {:>10} Dateien".format(k, v))
    context.logger.info(
        context._(
            "TOTAL: {} files.\nQUALIFIED: {} files (supported file extension)\n\n"
        ).format(
            context.statistics.total_files_found, context.statistics.files_processed
        )
    )

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
    context.logger.info(
        context._("Analysis finished at {}").format(context.statistics.end_time)
    )
    context.logger.info(
        context._("Performance of analysis: {} analyzed files per second").format(
            context.statistics.files_per_second
        )
    )

    # Output NER statistics if NER was used
    if (
        context.config.use_ner
        and context.statistics.ner_stats.total_chunks_processed > 0
    ):
        context.logger.info("\n" + context._("NER Statistics"))
        context.logger.info("------------")
        context.logger.info(
            context._("Chunks processed: {}").format(
                context.statistics.ner_stats.total_chunks_processed
            )
        )
        context.logger.info(
            context._("Entities found: {}").format(
                context.statistics.ner_stats.total_entities_found
            )
        )
        context.logger.info(
            context._("Total NER processing time: {:.2f}s").format(
                context.statistics.ner_stats.total_processing_time
            )
        )
        context.logger.info(
            context._("Average time per chunk: {:.3f}s").format(
                context.statistics.avg_ner_time_per_chunk
            )
        )
        if context.statistics.ner_stats.entities_by_type:
            context.logger.info(context._("Entities by type:"))
            for entity_type, count in sorted(
                context.statistics.ner_stats.entities_by_type.items(),
                key=lambda x: x[1],
                reverse=True,
            ):
                context.logger.info(f"  {entity_type}: {count}")
        if context.statistics.ner_stats.errors > 0:
            context.logger.warning(
                context._("NER errors encountered: {}").format(
                    context.statistics.ner_stats.errors
                )
            )

    # Prepare metadata for output writers
    output_metadata = {
        "start_time": (
            context.statistics.start_time.isoformat()
            if context.statistics.start_time
            else None
        ),
        "end_time": (
            context.statistics.end_time.isoformat()
            if context.statistics.end_time
            else None
        ),
        "duration_seconds": context.statistics.duration_seconds,
        "path": context.config.path,
        "methods": {
            "regex": context.config.use_regex,
            "ner": context.config.use_ner,
            "spacy_ner": getattr(context.config, "use_spacy_ner", False),
            "ollama": getattr(context.config, "use_ollama", False),
            "openai_compatible": getattr(
                context.config, "use_openai_compatible", False
            ),
            "multimodal": getattr(context.config, "use_multimodal", False),
            "pydantic_ai": getattr(context.config, "use_pydantic_ai", False),
        },
        "total_files": context.statistics.total_files_found,
        "analyzed_files": context.statistics.files_processed,
        "matches_found": context.statistics.matches_found,
        "error_count": context.statistics.total_errors,
        "statistics": context.statistics.get_summary_dict(),
        "file_extensions": dict(
            sorted(
                context.statistics.extension_counts.items(),
                key=lambda item: item[1],
                reverse=True,
            )
        ),
        "errors": [
            {"type": error_type, "files": file_list}
            for error_type, file_list in errors.items()
        ],
    }

    # Write output using writer
    if context.output_writer:
        # For non-streaming formats (JSON, XLSX), write all matches now
        if not context.output_writer.supports_streaming:
            # Write all matches that were collected during processing
            for pm in context.match_container.pii_matches:
                context.output_writer.write_match(pm)

        # Finalize output
        try:
            context.output_writer.finalize(metadata=output_metadata)
        except OutputError as e:
            context.logger.error(f"Failed to write output: {e}")
            raise typer.Exit(code=constants.EXIT_GENERAL_ERROR)
    else:
        # Fallback: Close CSV file handle if it exists
        if csv_file_handle:
            csv_file_handle.close()

    # Generate and write statistics output if statistics mode is enabled
    if statistics_aggregator:
        # Determine statistics output file path
        if hasattr(args, "statistics_output") and args.statistics_output:
            statistics_file_path = args.statistics_output
        else:
            # Auto-generate path in output directory
            statistics_file_path = output_dir + outslug + "_statistics.json"

        # Get aggregated statistics
        aggregated_stats = statistics_aggregator.get_statistics()

        # Prepare scan metadata
        scan_metadata = {
            "scan_id": outslug,
            "start_time": (
                context.statistics.start_time.isoformat()
                if context.statistics.start_time
                else None
            ),
            "end_time": (
                context.statistics.end_time.isoformat()
                if context.statistics.end_time
                else None
            ),
            "duration_seconds": round(context.statistics.duration_seconds, 2),
            "scan_path": context.config.path,
            "detection_methods": {
                "regex": context.config.use_regex,
                "ner": context.config.use_ner,
                "spacy_ner": getattr(context.config, "use_spacy_ner", False),
                "ollama": getattr(context.config, "use_ollama", False),
                "openai_compatible": getattr(
                    context.config, "use_openai_compatible", False
                ),
                "multimodal": getattr(context.config, "use_multimodal", False),
                "pydantic_ai": getattr(context.config, "use_pydantic_ai", False),
            },
            "total_files_scanned": context.statistics.total_files_found,
            "total_files_analyzed": context.statistics.files_processed,
            "total_matches_found": context.statistics.matches_found,
            "statistics_strict": bool(getattr(args, "statistics_strict", False)),
        }

        # Prepare performance metrics
        performance_metrics = {
            "files_per_second": context.statistics.files_per_second,
            "matches_per_second": round(
                (
                    context.statistics.matches_found
                    / context.statistics.duration_seconds
                    if context.statistics.duration_seconds > 0
                    else 0
                ),
                2,
            ),
            "processing_time_seconds": round(context.statistics.duration_seconds, 2),
        }

        # Add NER statistics if available
        if context.statistics.ner_stats.total_chunks_processed > 0:
            performance_metrics["ner_statistics"] = {
                "chunks_processed": context.statistics.ner_stats.total_chunks_processed,
                "entities_found": context.statistics.ner_stats.total_entities_found,
                "avg_time_per_chunk": round(
                    context.statistics.avg_ner_time_per_chunk, 3
                ),
                "errors": context.statistics.ner_stats.errors,
            }

        # Create statistics writer
        from core.writers import PrivacyStatisticsWriter

        stats_writer = PrivacyStatisticsWriter(statistics_file_path)

        # Write statistics
        try:
            stats_writer.finalize(
                metadata={
                    "statistics": aggregated_stats,
                    "scan_metadata": scan_metadata,
                    "performance_metrics": performance_metrics,
                }
            )
            context.logger.info(
                f"Privacy-focused statistics written to: {statistics_file_path}"
            )
        except OutputError as e:
            context.logger.error(f"Failed to write statistics output: {e}")
            # Don't fail the entire scan if statistics writing fails

    # Show summary to console (unless in quiet mode)
    if not (hasattr(args, "quiet") and args.quiet):
        summary_format = (
            getattr(args, "summary_format", "human")
            if hasattr(args, "summary_format")
            else "human"
        )

        if summary_format == "json":
            # Machine-readable JSON output
            import json

            summary_data = {
                "start_time": (
                    context.statistics.start_time.isoformat()
                    if context.statistics.start_time
                    else None
                ),
                "end_time": (
                    context.statistics.end_time.isoformat()
                    if context.statistics.end_time
                    else None
                ),
                "duration_seconds": context.statistics.duration_seconds,
                "statistics": {
                    "files_scanned": context.statistics.total_files_found,
                    "files_analyzed": context.statistics.files_processed,
                    "matches_found": context.statistics.matches_found,
                    "errors": context.statistics.total_errors,
                    "throughput_files_per_sec": context.statistics.files_per_second,
                },
                "output_file": context.output_file_path
                or output_file_path,
                "output_directory": output_dir,
                "errors_summary": (
                    {k: len(v) for k, v in errors.items()} if errors else {}
                ),
            }
            typer.echo(json.dumps(summary_data, indent=2))
        else:
            # Human-readable output
            typer.echo("\n" + "=" * 50)
            typer.echo(context._("Analysis Summary"))
            typer.echo("=" * 50)
            if context.statistics.start_time:
                typer.echo(
                    f"{context._('Started:')}     {context.statistics.start_time.strftime('%Y-%m-%d %H:%M:%S')}"
                )
            if context.statistics.end_time:
                typer.echo(
                    f"{context._('Finished:')}    {context.statistics.end_time.strftime('%Y-%m-%d %H:%M:%S')}"
                )
            typer.echo(f"{context._('Duration:')}    {context.statistics.duration}")
            typer.echo()
            typer.echo(context._("Statistics:"))
            typer.echo(
                f"  {context._('Files scanned:')}      {context.statistics.total_files_found:,}"
            )
            typer.echo(
                f"  {context._('Files analyzed:')}     {context.statistics.files_processed:,}"
            )
            typer.echo(
                f"  {context._('Matches found:')}      {context.statistics.matches_found:,}"
            )
            typer.echo(
                f"  {context._('Errors:')}             {context.statistics.total_errors:,}"
            )
            typer.echo()
            typer.echo(context._("Performance:"))
            typer.echo(
                f"  {context._('Throughput:')}         {context.statistics.files_per_second} {context._('files/sec')}"
            )
            typer.echo()
            if errors:
                typer.echo(context._("Errors Summary:"))
                for k, v in errors.items():
                    typer.echo(f"  {k}: {len(v)} {context._('files')}")
                typer.echo()

            # Get output file name
            output_file = context.output_file_path or output_file_path

            typer.echo(f"{context._('Output file:')} {output_file}")
            typer.echo(f"{context._('Output directory:')} {output_dir}")
            typer.echo("=" * 50 + "\n")


@app.command()
def doctor(
    json_output: bool = typer.Option(
        False, "--json", help="Output the doctor report as JSON."
    ),
    strict: bool = typer.Option(
        False,
        "--strict",
        help="Exit with non-zero status on warnings (not only errors).",
    ),
) -> None:
    """Validate configuration and optional dependencies."""
    report = run_doctor()
    if json_output:
        import json

        typer.echo(
            json.dumps(
                {
                    "ok": report.ok,
                    "issues": [
                        {"level": i.level, "message": i.message} for i in report.issues
                    ],
                    "details": report.details,
                },
                indent=2,
            )
        )
    else:
        status = "OK" if report.ok else "FAILED"
        typer.echo(f"Doctor: {status}")
        for issue in report.issues:
            typer.echo(f"- {issue.level.upper()}: {issue.message}")

    if not report.ok:
        raise typer.Exit(code=constants.EXIT_CONFIGURATION_ERROR)
    if strict and any(i.level == "warning" for i in report.issues):
        raise typer.Exit(code=constants.EXIT_CONFIGURATION_ERROR)

def cli() -> None:
    """Entry point for CLI - calls Typer app."""
    app()


if __name__ == "__main__":
    cli()
