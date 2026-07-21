"""CLI interface using Typer for modern command-line argument parsing."""

import argparse
import os
from pathlib import Path

import typer

# Import existing setup and processing logic
from core import cli_setup as setup
from core import constants
from core.config import Config
from core.config_loader import ConfigLoader
from core.doctor import run_doctor

# Create Typer app
app = typer.Typer(
    name="pbd-toolkit",
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
        from importlib.metadata import version

        return version("pbd-toolkit")
    except Exception:
        return getattr(constants, "VERSION", "unknown")


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"pbd-toolkit {_get_cli_version()}")
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


def _create_argparse_namespace_from_typer_args(**kwargs) -> argparse.Namespace:
    """Create an argparse Namespace from Typer arguments.

    This adapter allows us to use existing setup functions that expect argparse.Namespace.

    Args:
        **kwargs: All Typer command arguments

    Returns:
        Namespace with attributes matching the Typer arguments
    """
    return argparse.Namespace(**kwargs)


@app.command()
def scan(
    # Optional path (positional or flag). If neither is provided, it can come from --config.
    path: str | None = typer.Argument(
        None, help="Root directory under which to recursively search for PII"
    ),
    path_opt: str | None = typer.Option(
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
    openai_api_key: str | None = typer.Option(
        None, "--openai-api-key", help="OpenAI API key (or set OPENAI_API_KEY env var)"
    ),
    openai_model: str = typer.Option(
        "gpt-4o-mini",
        "--openai-model",
        help="OpenAI model to use (default: gpt-4o-mini)",
    ),
    # Multimodal image detection
    multimodal: bool = typer.Option(
        False, "--multimodal", help="Use multimodal models for image PII detection"
    ),
    multimodal_api_base: str | None = typer.Option(
        None,
        "--multimodal-api-base",
        help="Multimodal API base URL (defaults to --openai-api-base)",
    ),
    multimodal_api_key: str | None = typer.Option(
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
    pydantic_ai_model: str | None = typer.Option(
        None,
        "--pydantic-ai-model",
        help="Model name for PydanticAI (auto-determined from provider if not specified)",
    ),
    pydantic_ai_api_key: str | None = typer.Option(
        None,
        "--pydantic-ai-api-key",
        help="API key for PydanticAI (or use provider-specific env vars)",
    ),
    pydantic_ai_base_url: str | None = typer.Option(
        None,
        "--pydantic-ai-base-url",
        help="Base URL for PydanticAI (for custom endpoints)",
    ),
    # Vector search engine
    vector_search: bool = typer.Option(
        False,
        "--vector-search",
        help="Use vector-based semantic similarity for PII detection (requires: pip install sentence-transformers)",
    ),
    vector_triage: bool = typer.Option(
        False,
        "--vector-triage",
        help="Use vector search as a pre-filter: only chunks with a PII signal are forwarded to other engines (saves LLM API calls)",
    ),
    vector_model: str = typer.Option(
        "sentence-transformers/all-MiniLM-L6-v2",
        "--vector-model",
        help="Sentence-transformers model for vector search (default: all-MiniLM-L6-v2)",
    ),
    vector_threshold: float = typer.Option(
        0.75,
        "--vector-threshold",
        help="Cosine similarity threshold for vector PII detection (default: 0.75)",
    ),
    vector_save_index: str | None = typer.Option(
        None,
        "--vector-save-index",
        help="Path prefix to save the FAISS document index after scanning (enables cross-document analysis)",
    ),
    vector_load_index: str | None = typer.Option(
        None,
        "--vector-load-index",
        help="Path prefix of a previously saved FAISS index to load before scanning",
    ),
    vector_custom_exemplars: str | None = typer.Option(
        None,
        "--vector-custom-exemplars",
        help="Path to a YAML or JSON file with additional PII exemplar categories for vector search. "
        "Existing built-in categories are extended; new names add new detection categories.",
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
    outname: str | None = typer.Option(
        None,
        "--outname",
        help="Optional parameter; string which to include in the file name of all output files",
    ),
    whitelist: str | None = typer.Option(
        None,
        "--whitelist",
        help="Optional parameter; relative path to a text file containing one string per line. These strings will be matched against potential findings to exclude them from the output.",
    ),
    stop_count: int | None = typer.Option(
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
    jobs: int | None = typer.Option(
        None,
        "--jobs",
        help="Number of parallel file workers (overrides --mode).",
    ),
    no_header: bool = typer.Option(
        False,
        "--no-header",
        help="Don't include header row in CSV output (for backward compatibility)",
    ),
    deduplicate: bool = typer.Option(
        False,
        "--deduplicate",
        help="Remove duplicate findings with identical text, file, and type across all engines",
    ),
    confidence_fusion: bool = typer.Option(
        False,
        "--confidence-fusion",
        help="When multiple engines detect the same PII, merge their confidence scores (max + corroboration bonus). Implies deduplication.",
    ),
    structured_validation: bool = typer.Option(
        True,
        "--structured-validation/--no-structured-validation",
        help="Checksum-validate structured findings (IBAN, credit card, tax ID, BIC) from all engines, not just regex, discarding invalid ones (default: on).",
    ),
    text_chunk_size: int = typer.Option(
        0,
        "--text-chunk-size",
        help="Split large texts into overlapping chunks of this size for NER engines (0 = disabled). Recommended: 2000",
    ),
    text_chunk_overlap: int = typer.Option(
        200,
        "--text-chunk-overlap",
        help="Number of characters shared between adjacent text chunks (default: 200)",
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
    statistics_output: str | None = typer.Option(
        None,
        "--statistics-output",
        help="Path for statistics JSON output file (default: auto-generated in output directory)",
    ),
    # Confidence filtering
    min_confidence: float = typer.Option(
        0.0,
        "--min-confidence",
        help="Minimum confidence score (0.0-1.0) to include a finding. Regex matches without validation default to 0.8, validated matches to 1.0.",
    ),
    # Context extraction
    context_chars: int = typer.Option(
        0,
        "--context-chars",
        help="Number of surrounding characters to capture around each finding for context (0 = disabled, recommended: 50-100)",
    ),
    # Redaction
    redact: bool = typer.Option(
        False,
        "--redact",
        help="Create redacted copies of files with PII replaced by [REDACTED:TYPE] placeholders",
    ),
    redact_dir: str | None = typer.Option(
        None,
        "--redact-dir",
        help="Directory for redacted output files (default: output_dir/redacted/)",
    ),
    # Pseudo-anonymization
    pseudonymize: bool = typer.Option(
        False,
        "--pseudonymize",
        help="Create pseudo-anonymized copies with realistic fake values instead of [REDACTED:TYPE]",
    ),
    pseudonymize_dir: str | None = typer.Option(
        None,
        "--pseudonymize-dir",
        help="Directory for pseudo-anonymized output files (default: output_dir/pseudonymized/)",
    ),
    # Webhook notification
    webhook_url: str | None = typer.Option(
        None,
        "--webhook-url",
        help="POST scan summary as JSON to this URL when the scan completes",
    ),
    # Incremental scanning
    incremental: bool = typer.Option(
        False,
        "--incremental",
        help="Skip files whose content has not changed since the last scan (SHA-256 + mtime cache).",
    ),
    cache_path: str | None = typer.Option(
        None,
        "--cache-path",
        help="Path to the incremental scan cache database (default: .pbd_scan_cache.db in the output directory).",
    ),
    # Output options
    verbose: bool = typer.Option(
        False, "-v", "--verbose", help="Enable verbose output with detailed logging"
    ),
    quiet: bool = typer.Option(
        False, "-q", "--quiet", help="Suppress all output except errors"
    ),
    # Config file
    config: Path | None = typer.Option(
        None,
        "--config",
        help="Path to configuration file (YAML or JSON). CLI arguments override config file values.",
    ),
    # Analytics
    analytics: bool = typer.Option(
        False,
        "--analytics",
        help="Persist scan results to an analytics database for dashboards and trend analysis (no PII text stored)",
    ),
    analytics_db: str = typer.Option(
        ".pbd_analytics.db",
        "--analytics-db",
        help="Path to the analytics database file (default: .pbd_analytics.db)",
    ),
    # Severity filtering and CI/CD gate
    min_severity: str | None = typer.Option(
        None,
        "--min-severity",
        help="Only include findings at or above this severity in output: LOW, MEDIUM, HIGH, CRITICAL",
        case_sensitive=False,
    ),
    fail_on_severity: str | None = typer.Option(
        None,
        "--fail-on-severity",
        help="Exit with code 5 if any finding at or above this severity is found (for CI/CD pipelines): LOW, MEDIUM, HIGH, CRITICAL",
        case_sensitive=False,
    ),
    # Path exclusion
    exclude: list[str] = typer.Option(
        [],
        "--exclude",
        help="Glob pattern to exclude from scanning (can be repeated). E.g. 'tests/', '**/*.bak'",
    ),
    # Scan profile
    profile: str | None = typer.Option(
        None,
        "--profile",
        help="Load a built-in scan profile (quick, standard, deep, gdpr-audit, ci, medical, credentials). CLI arguments override profile values.",
        case_sensitive=False,
    ),
) -> None:
    """Scan directory for PII using specified detection methods.

    At least one detection method must be enabled (--regex, --ner, --spacy-ner,
    --ollama, --openai-compatible, --multimodal, or --pydantic-ai).
    """
    # Disable telemetry in dependencies for privacy
    setup.__check_telemetry_settings()

    # Apply environment variable overrides for unset CLI options.
    env_overrides = ConfigLoader.load_env_overrides()
    if config is None and "config" in env_overrides:
        config = Path(env_overrides["config"])
    if output_dir == "./output/" and "output_dir" in env_overrides:
        output_dir = env_overrides["output_dir"]

    # Setup language handling
    translate_func = setup.__setup_lang()

    # Deprecation warning for --path option (prefer positional PATH argument).
    if path_opt is not None:
        typer.echo(
            "Warning: --path is deprecated. Pass the directory as a positional argument instead: "
            "pbd-toolkit scan /your/directory",
            err=True,
        )

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
        "vector_search": vector_search,
        "vector_triage": vector_triage,
        "vector_model": vector_model,
        "vector_threshold": vector_threshold,
        "vector_save_index": vector_save_index,
        "vector_load_index": vector_load_index,
        "vector_custom_exemplars": vector_custom_exemplars,
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
        "deduplicate": deduplicate,
        "confidence_fusion": confidence_fusion,
        "structured_validation": structured_validation,
        "text_chunk_size": text_chunk_size,
        "text_chunk_overlap": text_chunk_overlap,
        "statistics_mode": statistics_mode,
        "statistics_strict": statistics_strict,
        "statistics_output": statistics_output,
        "verbose": verbose,
        "quiet": quiet,
        "config": config,
        "incremental": incremental,
        "cache_path": cache_path,
        "redact": redact,
        "redact_dir": redact_dir,
        "pseudonymize": pseudonymize,
        "pseudonymize_dir": pseudonymize_dir,
        "webhook_url": webhook_url,
        "context_chars": context_chars,
        "min_confidence": min_confidence,
        "analytics": analytics,
        "analytics_db": analytics_db,
        "min_severity": min_severity.upper() if min_severity else None,
        "fail_on_severity": fail_on_severity.upper() if fail_on_severity else None,
        "exclude": list(exclude),
    }

    args = _create_argparse_namespace_from_typer_args(**typer_args)

    # Deprecation warnings for legacy engine flags.
    if ollama:
        typer.echo(
            "Warning: --ollama is deprecated. Use --pydantic-ai --pydantic-ai-provider ollama instead.",
            err=True,
        )
    if openai_compatible:
        typer.echo(
            "Warning: --openai-compatible is deprecated. Use --pydantic-ai --pydantic-ai-provider openai instead.",
            err=True,
        )

    # Load scan profile if provided (applied before config file so config can override)
    if profile:
        from core.profiles import get_profile

        try:
            profile_data = get_profile(profile)
            args = ConfigLoader.merge_with_args(profile_data, args)
        except ValueError as e:
            typer.echo(f"Profile error: {e}", err=True)
            raise typer.Exit(code=constants.EXIT_CONFIGURATION_ERROR)

    # Load config file if provided
    if config:
        try:
            config_data = ConfigLoader.load_config(config)
            args = ConfigLoader.merge_with_args(config_data, args)
        except (ValueError, FileNotFoundError, PermissionError) as e:
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

    # --- Early path validation ---
    scan_path = getattr(args, "path")
    if not os.path.exists(scan_path):
        typer.echo(f"Scan path does not exist: {scan_path}", err=True)
        raise typer.Exit(code=constants.EXIT_INVALID_ARGUMENTS)
    if not os.path.isdir(scan_path):
        typer.echo(f"Scan path is not a directory: {scan_path}", err=True)
        raise typer.Exit(code=constants.EXIT_INVALID_ARGUMENTS)
    if not os.access(scan_path, os.R_OK):
        typer.echo(f"Scan path is not readable: {scan_path}", err=True)
        raise typer.Exit(code=constants.EXIT_INVALID_ARGUMENTS)

    whitelist_arg = getattr(args, "whitelist", None)
    if whitelist_arg and not os.path.isfile(whitelist_arg):
        typer.echo(f"Whitelist file not found: {whitelist_arg}", err=True)
        raise typer.Exit(code=constants.EXIT_INVALID_ARGUMENTS)

    # Construct name for output files
    import datetime
    import re as _re

    outslug: str = datetime.datetime.now().strftime("%Y-%m-%d %H-%M-%S")
    if args.outname is not None:
        # Sanitize outname: remove path separators and other characters that
        # could cause the output file to be written outside the output directory.
        safe_outname = _re.sub(r"[/\\<>:\"|?*\x00-\x1f]", "_", args.outname)
        outslug += " " + safe_outname

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
    extension_map = {
        "csv": ".csv",
        "json": ".json",
        "jsonl": ".jsonl",
        "xlsx": ".xlsx",
        "html": ".html",
        "sarif": ".sarif",
    }
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
        # Other configuration errors: keep the specific exception type visible
        # instead of collapsing every cause into the same generic message.
        typer.echo(f"Configuration error: {type(e).__name__}: {e}", err=True)
        logger.debug("Configuration error details", exc_info=True)
        raise typer.Exit(code=constants.EXIT_CONFIGURATION_ERROR)

    # Apply extra CLI flags to config object
    _use_fusion = bool(getattr(args, "confidence_fusion", False))
    config_obj.enable_deduplication = (
        bool(getattr(args, "deduplicate", False)) or _use_fusion
    )
    _chunk_size = getattr(args, "text_chunk_size", 0)
    if isinstance(_chunk_size, int) and _chunk_size >= 0:
        config_obj.text_chunk_size = _chunk_size
    _chunk_overlap = getattr(args, "text_chunk_overlap", 200)
    if isinstance(_chunk_overlap, int) and _chunk_overlap >= 0:
        config_obj.text_chunk_overlap = _chunk_overlap
    _context_chars = getattr(args, "context_chars", 0)
    if isinstance(_context_chars, int) and _context_chars >= 0:
        config_obj.context_chars = _context_chars
    _min_conf = getattr(args, "min_confidence", 0.0)
    if isinstance(_min_conf, (int, float)):
        config_obj.min_confidence = float(_min_conf)
    _min_sev = getattr(args, "min_severity", None)
    if _min_sev:
        config_obj.min_severity = _min_sev.upper()
    _fail_sev = getattr(args, "fail_on_severity", None)
    if _fail_sev:
        config_obj.fail_on_severity = _fail_sev.upper()
    _exclude = getattr(args, "exclude", [])
    if _exclude:
        config_obj.exclude_patterns = list(_exclude)

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
        getattr(config_obj, "use_vector_search", False),
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

    # Detection-flag interpretation. The shared :class:`~core.scan_runner.ScanRunner`
    # builds the actual PiiMatchContainer / Statistics / ApplicationContext from
    # these (and from the config + output wiring assembled above), so the CLI and
    # the REST API share one orchestration path (issue #76).
    _dedup_enabled = bool(getattr(args, "deduplicate", False))
    _fusion_enabled = bool(getattr(args, "confidence_fusion", False))
    _min_conf_val = config_obj.min_confidence
    _structured_validation = bool(getattr(args, "structured_validation", True))
    _statistics_mode = bool(getattr(args, "statistics_mode", False))
    _statistics_strict = bool(getattr(args, "statistics_strict", False))

    # Analytics database (optional)
    _analytics_enabled = getattr(args, "analytics", False)
    _analytics_db_path = getattr(args, "analytics_db", ".pbd_analytics.db")
    analytics_store = None
    analytics_session_id = None
    if _analytics_enabled:
        try:
            from analytics.store import AnalyticsStore

            analytics_store = AnalyticsStore(db_path=_analytics_db_path, logger=logger)
            config_summary = {
                "engines": [
                    name
                    for name, flag in [
                        ("regex", config_obj.use_regex),
                        ("gliner", config_obj.use_ner),
                        ("spacy", config_obj.use_spacy_ner),
                        ("ollama", config_obj.use_ollama),
                        ("openai", config_obj.use_openai_compatible),
                        ("pydantic-ai", config_obj.use_pydantic_ai),
                        ("vector", config_obj.use_vector_search),
                    ]
                    if flag
                ],
                "profile": getattr(args, "profile", None),
                "deduplicate": config_obj.enable_deduplication,
                "incremental": config_obj.use_incremental,
            }
            analytics_session_id = analytics_store.create_session(
                scan_path=config_obj.path,
                config_summary=config_summary,
                source="cli",
            )
            logger.info(
                translate_func("Analytics database enabled: %s") % _analytics_db_path
            )
        except Exception as exc:
            logger.warning("Failed to initialize analytics database: %s", exc)

    # Worker count: CLI mode/jobs flags decide concurrency; the runner owns the
    # executor lifecycle (issue #79).
    mode_lower = (getattr(args, "mode", "balanced") or "balanced").lower()
    cpu_count = os.cpu_count() or 4
    if getattr(args, "jobs", None):
        worker_count = max(1, int(args.jobs))
    elif mode_lower == "safe":
        worker_count = 1
    elif mode_lower == "fast":
        worker_count = min(32, max(2, cpu_count * 4))
    else:
        worker_count = max(1, cpu_count)

    # --- Delegate the scan pipeline to the shared ScanRunner -------------------
    from core import scan_reporting
    from core.scan_runner import ScanRequest, ScanRunner

    run_result = ScanRunner().run(
        ScanRequest(
            config=config_obj,
            logger=logger,
            translate_func=translate_func,
            output_writer=output_writer,
            output_format=output_format,
            output_file_path=output_file_path,
            output_dir=output_dir,
            outslug=outslug,
            csv_writer=csv_writer,
            csv_file_handle=csv_file_handle,
            enable_deduplication=_dedup_enabled,
            enable_confidence_fusion=_fusion_enabled,
            validate_structured_findings=_structured_validation,
            min_confidence=_min_conf_val,
            worker_count=worker_count,
            incremental=bool(getattr(args, "incremental", False)),
            cache_path=getattr(args, "cache_path", None),
            statistics_mode=_statistics_mode,
            statistics_strict=_statistics_strict,
            statistics_output=getattr(args, "statistics_output", None),
            analytics_store=analytics_store,
            analytics_session_id=analytics_session_id,
            finalize_analytics_session=True,
            fail_on_severity=getattr(args, "fail_on_severity", None),
        )
    )

    # Bind result objects for the CLI-owned post-scan side effects below.
    context = run_result.context
    errors = run_result.errors
    file_risk_scores = run_result.file_risk_scores
    matches_by_file = run_result.matches_by_file

    # The runner writes output internally and translates OutputError into an
    # exit code rather than raising ``typer.Exit``.  Surface write failures here
    # before running side effects, mirroring the legacy ordering.
    if run_result.exit_code not in (
        constants.EXIT_SUCCESS,
        constants.EXIT_FINDINGS_ABOVE_THRESHOLD,
    ):
        raise typer.Exit(code=run_result.exit_code)

    # Redaction: create redacted copies if requested
    if getattr(args, "redact", False) and matches_by_file:
        from core.redactor import redact_files

        _redact_dir = getattr(args, "redact_dir", None) or os.path.join(
            output_dir, "redacted"
        )
        redacted_paths = redact_files(
            matches_by_file=matches_by_file,
            output_dir=_redact_dir,
            logger=context.logger,
        )
        if redacted_paths and not (hasattr(args, "quiet") and args.quiet):
            typer.echo(f"\nRedacted {len(redacted_paths)} files to: {_redact_dir}")

    # Pseudo-anonymization: create files with realistic fake replacements
    if getattr(args, "pseudonymize", False) and matches_by_file:
        from core.pseudonymizer import pseudonymize_files

        _pseudo_dir = getattr(args, "pseudonymize_dir", None) or os.path.join(
            output_dir, "pseudonymized"
        )
        pseudo_paths = pseudonymize_files(
            matches_by_file=matches_by_file,
            output_dir=_pseudo_dir,
            logger=context.logger,
        )
        if pseudo_paths and not (hasattr(args, "quiet") and args.quiet):
            typer.echo(
                f"\nPseudo-anonymized {len(pseudo_paths)} files to: {_pseudo_dir}"
            )

    # Webhook: POST scan summary to configured URL
    _webhook_url = getattr(args, "webhook_url", None)
    if _webhook_url:
        import json as _json

        try:
            import urllib.request as _urllib_req

            _summary_payload = {
                "scan_path": str(config_obj.path),
                "total_findings": len(context.match_container.pii_matches),
                "files_scanned": context.statistics.files_processed,
                "duration_sec": context.statistics.duration_seconds,
                "severity_counts": {
                    sev: sum(
                        1
                        for m in context.match_container.pii_matches
                        if m.severity == sev
                    )
                    for sev in ("CRITICAL", "HIGH", "MEDIUM", "LOW")
                },
                "output_file": output_file_path,
            }
            _req = _urllib_req.Request(
                _webhook_url,
                data=_json.dumps(_summary_payload).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with _urllib_req.urlopen(_req, timeout=10) as _resp:  # noqa: S310  # nosec B310
                _status = _resp.status
            if not (hasattr(args, "quiet") and args.quiet):
                typer.echo(f"\nWebhook delivered (HTTP {_status}): {_webhook_url}")
        except Exception as _exc:
            typer.echo(f"\nWebhook delivery failed: {_exc}", err=True)

    # Console summary
    if not (hasattr(args, "quiet") and args.quiet):
        summary_fmt = (
            getattr(args, "summary_format", "human")
            if hasattr(args, "summary_format")
            else "human"
        )
        scan_reporting.print_console_summary(
            context,
            errors,
            file_risk_scores,
            matches_by_file,
            output_file_path,
            output_dir,
            summary_format=summary_fmt,
        )

    # CI/CD severity gate: exit with code 5 if threshold is exceeded. The runner
    # already computed the decision; the CLI owns the message + exit semantics.
    _fail_sev = getattr(args, "fail_on_severity", None)
    if _fail_sev and run_result.findings_above_threshold:
        if not (hasattr(args, "quiet") and args.quiet):
            typer.echo(
                f"\n[fail-on-severity] Findings at or above {_fail_sev.upper()} detected. Exiting with code {constants.EXIT_FINDINGS_ABOVE_THRESHOLD}.",
                err=True,
            )
        raise typer.Exit(code=constants.EXIT_FINDINGS_ABOVE_THRESHOLD)


@app.command()
def query(
    index: str = typer.Argument(
        ...,
        help="Path prefix of the saved FAISS index (same value used for --vector-save-index during scanning)",
    ),
    query_text: str | None = typer.Argument(
        None,
        help="Text to search for semantically similar document chunks",
    ),
    query_opt: str | None = typer.Option(
        None,
        "--query",
        "-q",
        help="Query text (alternative to the positional argument)",
    ),
    top_k: int = typer.Option(
        5,
        "--top-k",
        "-k",
        help="Maximum number of results to return (default: 5)",
    ),
    threshold: float = typer.Option(
        0.70,
        "--threshold",
        help="Minimum cosine similarity score 0.0–1.0 (default: 0.70)",
    ),
    model: str = typer.Option(
        "sentence-transformers/all-MiniLM-L6-v2",
        "--model",
        help="Embedding model name (must match the model used during the scan)",
    ),
    output_format: str = typer.Option(
        "human",
        "--format",
        help="Output format: 'human' (default) or 'json'",
        case_sensitive=False,
    ),
) -> None:
    """Query a saved vector index for semantically similar document chunks.

    The index must have been created during a scan with [bold]--vector-save-index[/bold].

    [bold]Examples:[/bold]

        pbd-toolkit query ./my_index "Name und Adresse des Kunden"

        pbd-toolkit query ./my_index --query "credit card number" --top-k 10

        pbd-toolkit query ./my_index -q "Krankenversicherungsnummer" --format json
    """
    resolved_query = query_opt or query_text
    if not resolved_query:
        typer.echo(
            "Error: provide query text as a positional argument or via --query / -q",
            err=True,
        )
        raise typer.Exit(code=constants.EXIT_INVALID_ARGUMENTS)

    # Validate that index metadata file exists
    meta_path = index + ".meta"
    if not os.path.isfile(meta_path):
        typer.echo(
            f"Error: Index metadata file not found: {meta_path}\n"
            "Run a scan with --vector-save-index to create an index first.",
            err=True,
        )
        raise typer.Exit(code=constants.EXIT_INVALID_ARGUMENTS)

    from core.indexer.document_indexer import DocumentIndexer

    indexer = DocumentIndexer(
        model_name=model,
        load_index_path=index,
        verbose=False,
    )

    if not indexer.is_available():
        typer.echo(
            "Error: sentence-transformers is not installed.\n"
            "Install with:  pip install sentence-transformers\n"
            "           or: pip install 'pbd-toolkit[vector]'",
            err=True,
        )
        raise typer.Exit(code=constants.EXIT_CONFIGURATION_ERROR)

    typer.echo(f"Loading index from '{index}' …", err=True)
    try:
        results = indexer.query_similar_chunks(
            resolved_query, top_k=top_k, threshold=threshold
        )
    except Exception as exc:
        typer.echo(f"Error querying index: {exc}", err=True)
        raise typer.Exit(code=constants.EXIT_GENERAL_ERROR)

    num_indexed = indexer.num_indexed_chunks

    if output_format.lower() == "json":
        import json

        output = {
            "query": resolved_query,
            "index": index,
            "index_size": num_indexed,
            "top_k": top_k,
            "threshold": threshold,
            "results": [
                {
                    "rank": i + 1,
                    "score": round(score, 4),
                    "file": chunk.file_path,
                    "chunk_idx": chunk.chunk_idx,
                    "text": chunk.text,
                }
                for i, (score, chunk) in enumerate(results)
            ],
        }
        typer.echo(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        typer.echo(f"\nQuery:     {resolved_query!r}")
        typer.echo(f"Index:     {index}  ({num_indexed:,} chunks indexed)")
        typer.echo(f"Threshold: {threshold}   Top-k: {top_k}\n")
        if not results:
            typer.echo(f"No results found above threshold {threshold}.")
        else:
            sep = "─" * 72
            typer.echo(f"Found {len(results)} result(s):\n")
            for i, (score, chunk) in enumerate(results, 1):
                typer.echo(sep)
                typer.echo(
                    f"#{i}  Score: {score:.4f}  │  File: {chunk.file_path}  │  Chunk #{chunk.chunk_idx}"
                )
                preview = chunk.text.replace("\n", " ").strip()
                if len(preview) > 300:
                    preview = preview[:300] + " …"
                typer.echo(f"    {preview}")
            typer.echo(sep)


@app.command()
def evaluate(
    dataset: str = typer.Argument(
        ...,
        help="Path to an annotated ground-truth dataset (JSON). See eval/datasets/synthetic_de.json.",
    ),
    engines: str = typer.Option(
        "regex",
        "--engines",
        help="Comma-separated engines to evaluate: regex,gliner,spacy-ner,vector-search,pydantic-ai. Default 'regex' (offline, no model downloads).",
    ),
    output_format: str = typer.Option(
        "human",
        "--format",
        help="Output format: 'human' (default) or 'json'",
        case_sensitive=False,
    ),
    fail_under: float | None = typer.Option(
        None,
        "--fail-under",
        help="Exit non-zero if the micro-averaged F1 is below this value (0.0-1.0). Useful as a CI quality gate.",
    ),
) -> None:
    """Measure detection precision/recall/F1 against an annotated ground-truth dataset.

    Findings are produced through the real detection pipeline (canonical type
    normalisation + structured checksum validation), then matched to gold annotations
    by canonical entity type and span overlap.

    [bold]Examples:[/bold]

        pbd-toolkit evaluate eval/datasets/synthetic_de.json

        pbd-toolkit evaluate eval/datasets/synthetic_de.json --engines regex --format json

        pbd-toolkit evaluate eval/datasets/synthetic_de.json --fail-under 0.9
    """
    import json as _json

    from eval.dataset import load_dataset
    from eval.runner import run_evaluation

    engine_list = [e.strip() for e in engines.split(",") if e.strip()]

    try:
        documents = load_dataset(dataset)
    except FileNotFoundError:
        typer.echo(f"Error: dataset file not found: {dataset}", err=True)
        raise typer.Exit(code=constants.EXIT_INVALID_ARGUMENTS)
    except ValueError as exc:
        typer.echo(f"Error: invalid dataset: {exc}", err=True)
        raise typer.Exit(code=constants.EXIT_INVALID_ARGUMENTS)

    try:
        result = run_evaluation(documents, engine_list)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=constants.EXIT_INVALID_ARGUMENTS)

    report = result.as_dict()
    micro_f1 = report["micro"]["f1"]

    if output_format.lower() == "json":
        typer.echo(
            _json.dumps(
                {
                    "dataset": dataset,
                    "engines": engine_list,
                    "documents": len(documents),
                    **report,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
    else:
        typer.echo(f"\nDataset:   {dataset}  ({len(documents)} documents)")
        typer.echo(f"Engines:   {', '.join(engine_list)}\n")
        header = f"{'Type':<20}{'P':>8}{'R':>8}{'F1':>8}{'TP':>6}{'FP':>6}{'FN':>6}"
        typer.echo(header)
        typer.echo("─" * len(header))
        for typ, m in report["per_type"].items():
            typer.echo(
                f"{typ:<20}{m['precision']:>8.3f}{m['recall']:>8.3f}"
                f"{m['f1']:>8.3f}{m['tp']:>6}{m['fp']:>6}{m['fn']:>6}"
            )
        typer.echo("─" * len(header))
        micro = report["micro"]
        typer.echo(
            f"{'micro':<20}{micro['precision']:>8.3f}{micro['recall']:>8.3f}"
            f"{micro['f1']:>8.3f}{micro['tp']:>6}{micro['fp']:>6}{micro['fn']:>6}"
        )
        typer.echo(f"{'macro F1':<20}{report['macro_f1']:>8.3f}\n")

    if fail_under is not None and micro_f1 < fail_under:
        typer.echo(
            f"Quality gate FAILED: micro F1 {micro_f1:.4f} < --fail-under {fail_under}",
            err=True,
        )
        raise typer.Exit(code=constants.EXIT_GENERAL_ERROR)


@app.command("eval-extraction")
def eval_extraction(
    manifest: str = typer.Argument(
        ...,
        help="Path to an extraction manifest (JSON). See eval/datasets/extraction/manifest.json.",
    ),
    output_format: str = typer.Option(
        "human",
        "--format",
        help="Output format: 'human' (default) or 'json'",
        case_sensitive=False,
    ),
    fail_under: float | None = typer.Option(
        None,
        "--fail-under",
        help="Exit non-zero if extraction recall is below this value (0.0-1.0). Useful as a CI quality gate.",
    ),
) -> None:
    """Measure text-extraction recall of the file processors against a manifest.

    Runs the real FileProcessorRegistry extraction path over each listed file and
    checks which expected snippets appear in the extracted text.  This catches
    extraction regressions (e.g. a DOCX table or CSV column-header context going
    missing) that detection metrics alone cannot see.

    [bold]Examples:[/bold]

        pbd-toolkit eval-extraction eval/datasets/extraction/manifest.json

        pbd-toolkit eval-extraction eval/datasets/extraction/manifest.json --fail-under 1.0
    """
    import json as _json

    from eval.extraction import run_extraction_eval

    try:
        result = run_extraction_eval(manifest)
    except FileNotFoundError:
        typer.echo(f"Error: manifest file not found: {manifest}", err=True)
        raise typer.Exit(code=constants.EXIT_INVALID_ARGUMENTS)
    except ValueError as exc:
        typer.echo(f"Error: invalid manifest: {exc}", err=True)
        raise typer.Exit(code=constants.EXIT_INVALID_ARGUMENTS)

    report = result.as_dict()

    if output_format.lower() == "json":
        typer.echo(
            _json.dumps({"manifest": manifest, **report}, indent=2, ensure_ascii=False)
        )
    else:
        typer.echo(f"\nManifest:  {manifest}  ({len(report['per_file'])} files)\n")
        header = f"{'File':<32}{'Found':>8}{'Exp':>6}"
        typer.echo(header)
        typer.echo("─" * len(header))
        for r in report["per_file"]:
            typer.echo(f"{r['file']:<32}{r['found']:>8}{r['expected']:>6}")
            for miss in r["missing"]:
                typer.echo(f"    MISSING: {miss!r}")
            for hit in r["forbidden_hits"]:
                typer.echo(f"    FORBIDDEN LEAKED: {hit!r}")
        typer.echo("─" * len(header))
        typer.echo(
            f"Extraction recall: {report['recall']:.3f} "
            f"({report['total_found']}/{report['total_expected']} snippets)"
        )
        if report["forbidden_hits"]:
            typer.echo(f"Forbidden snippets leaked: {report['forbidden_hits']}")
        typer.echo("")

    if report["forbidden_hits"]:
        typer.echo(
            f"Extraction gate FAILED: {report['forbidden_hits']} forbidden snippet(s) leaked",
            err=True,
        )
        raise typer.Exit(code=constants.EXIT_GENERAL_ERROR)
    if fail_under is not None and result.recall < fail_under:
        typer.echo(
            f"Extraction gate FAILED: recall {result.recall:.4f} < --fail-under {fail_under}",
            err=True,
        )
        raise typer.Exit(code=constants.EXIT_GENERAL_ERROR)


@app.command()
def diff(
    old_file: str = typer.Argument(
        ..., help="Path to the baseline (old) findings file (JSON or JSONL)"
    ),
    new_file: str = typer.Argument(
        ..., help="Path to the current (new) findings file (JSON or JSONL)"
    ),
    output_format: str = typer.Option(
        "human",
        "--format",
        help="Output format: 'human' (default) or 'json'",
        case_sensitive=False,
    ),
) -> None:
    """Compare two scan result files to show new, removed, and unchanged findings.

    Useful for tracking remediation progress over time.

    [bold]Examples:[/bold]

        pbd-toolkit diff old_findings.json new_findings.json

        pbd-toolkit diff baseline.jsonl current.jsonl --format json
    """
    import json

    from core.diff import compute_diff, load_findings

    try:
        old_findings = load_findings(old_file)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        typer.echo(f"Error reading old file: {e}", err=True)
        raise typer.Exit(code=constants.EXIT_INVALID_ARGUMENTS)

    try:
        new_findings = load_findings(new_file)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        typer.echo(f"Error reading new file: {e}", err=True)
        raise typer.Exit(code=constants.EXIT_INVALID_ARGUMENTS)

    result = compute_diff(old_findings, new_findings)

    if output_format.lower() == "json":
        import json as _json

        typer.echo(_json.dumps(result, indent=2, ensure_ascii=False))
    else:
        s = result["summary"]
        typer.echo("\n" + "=" * 50)
        typer.echo("Scan Diff Report")
        typer.echo("=" * 50)
        typer.echo(f"  Old scan: {s['old_total']} findings ({old_file})")
        typer.echo(f"  New scan: {s['new_total']} findings ({new_file})")
        typer.echo()
        typer.echo(f"  New findings:       +{s['added']}")
        typer.echo(f"  Resolved findings:  -{s['removed']}")
        typer.echo(f"  Unchanged:           {s['unchanged']}")

        if result["added_by_severity"]:
            typer.echo("\n  New findings by severity:")
            for sev in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
                count = result["added_by_severity"].get(sev, 0)
                if count:
                    typer.echo(f"    {sev}: +{count}")

        if result["removed_by_severity"]:
            typer.echo("\n  Resolved findings by severity:")
            for sev in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
                count = result["removed_by_severity"].get(sev, 0)
                if count:
                    typer.echo(f"    {sev}: -{count}")

        # Show top new CRITICAL/HIGH findings
        critical_new = [
            f
            for f in result["added_findings"]
            if f.get("severity") in ("CRITICAL", "HIGH")
        ]
        if critical_new:
            typer.echo("\n  New CRITICAL/HIGH findings:")
            for f in critical_new[:10]:
                typer.echo(
                    f"    [{f.get('severity')}] {f.get('file')} - {f.get('type')}: {f.get('text', '')[:60]}"
                )

        typer.echo("=" * 50 + "\n")


@app.command()
def report(
    db: str = typer.Option(
        ".pbd_analytics.db",
        "--db",
        help="Path to the analytics database (default: .pbd_analytics.db)",
    ),
    last: int = typer.Option(
        10,
        "--last",
        help="Number of recent scan sessions to display (default: 10)",
    ),
    output_format: str = typer.Option(
        "human",
        "--format",
        help="Output format: 'human' (default) or 'json'",
        case_sensitive=False,
    ),
) -> None:
    """Show historical scan statistics from the analytics database.

    Requires a database populated with [bold]--analytics[/bold] during scanning.

    [bold]Examples:[/bold]

        pbd-toolkit report

        pbd-toolkit report --db /path/to/.pbd_analytics.db --last 20

        pbd-toolkit report --format json
    """
    import json as _json
    import os as _os

    if not _os.path.isfile(db):
        typer.echo(
            f"Error: Analytics database not found: {db}\n"
            "Run a scan with --analytics to create one.",
            err=True,
        )
        raise typer.Exit(code=constants.EXIT_INVALID_ARGUMENTS)

    try:
        from analytics.database import AnalyticsDatabase
        from analytics.queries import AnalyticsQueries
    except ImportError as exc:
        typer.echo(f"Error: could not load analytics module: {exc}", err=True)
        raise typer.Exit(code=constants.EXIT_GENERAL_ERROR)

    db_obj = AnalyticsDatabase(db_path=db)
    queries = AnalyticsQueries(db=db_obj)

    sessions_result = queries.get_sessions(limit=last)
    sessions = sessions_result.get("sessions", [])
    total_sessions = sessions_result.get("total", 0)
    severity_overall = queries.get_severity_breakdown()
    top_types = queries.get_pii_type_distribution()[:5]

    if output_format.lower() == "json":
        output = {
            "database": db,
            "total_sessions": total_sessions,
            "sessions": sessions,
            "overall_severity_breakdown": severity_overall,
            "top_pii_types": top_types,
        }
        typer.echo(_json.dumps(output, indent=2, ensure_ascii=False))
        return

    # Human-readable output
    typer.echo("\n" + "=" * 60)
    typer.echo("Analytics Report")
    typer.echo("=" * 60)
    typer.echo(f"  Database:       {db}")
    typer.echo(f"  Total sessions: {total_sessions}")
    typer.echo()

    if not sessions:
        typer.echo("  No scan sessions found.")
    else:
        typer.echo(f"  Last {min(last, len(sessions))} session(s):")
        typer.echo()
        for s in sessions:
            started = (s.get("started_at") or "")[:16]
            scan_path = s.get("scan_path") or "?"
            total_findings = s.get("total_findings") or 0
            critical = s.get("critical_findings") or 0
            high = s.get("high_findings") or 0
            duration = s.get("duration_seconds")
            dur_str = f"{duration:.1f}s" if duration is not None else "?"
            typer.echo(
                f"  {started}  {scan_path:<30}  "
                f"{total_findings:>4} findings  "
                f"({critical} CRITICAL, {high} HIGH)  {dur_str}"
            )

    if severity_overall:
        typer.echo()
        typer.echo("  Overall severity distribution (all sessions):")
        for row in severity_overall:
            typer.echo(f"    {row['severity']:<10} {row['count']:>6}")

    if top_types:
        typer.echo()
        typer.echo("  Top PII types (all sessions):")
        for row in top_types:
            typer.echo(f"    {row['pii_type']:<35} {row['count']:>6}")

    typer.echo("=" * 60 + "\n")


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


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host", help="Bind address"),
    port: int = typer.Option(8000, "--port", help="Port number"),
    analytics_db: str = typer.Option(
        ".pbd_analytics.db", "--analytics-db", help="Path to analytics database"
    ),
    reload: bool = typer.Option(
        False, "--reload", help="Auto-reload on code changes (dev only)"
    ),
    api_key: str | None = typer.Option(
        None, "--api-key", help="API key for Bearer auth (or PBD_API_KEY env)"
    ),
    allowed_scan_roots: str | None = typer.Option(
        None,
        "--allowed-scan-roots",
        help="Comma-separated allowed scan directories (default: cwd)",
    ),
    cors_origins: str | None = typer.Option(
        None, "--cors-origins", help="Comma-separated allowed CORS origins"
    ),
) -> None:
    """Start the REST API server for scanning and analytics."""
    try:
        from api.server import main as serve_main
    except ImportError:
        typer.echo(
            "The API module requires additional dependencies.\n"
            "Install them with:  pip install 'pbd-toolkit[api]'",
            err=True,
        )
        raise typer.Exit(code=constants.EXIT_CONFIGURATION_ERROR)

    argv = ["--host", host, "--port", str(port), "--analytics-db", analytics_db]
    if reload:
        argv.append("--reload")
    if api_key:
        argv.extend(["--api-key", api_key])
    if allowed_scan_roots:
        argv.extend(["--allowed-scan-roots", allowed_scan_roots])
    if cors_origins:
        argv.extend(["--cors-origins", cors_origins])
    serve_main(argv)


@app.command("install-hook")
def install_hook(
    hook_type: str = typer.Option(
        "pre-commit",
        "--hook-type",
        help="Git hook type to install (default: pre-commit)",
    ),
    engines: str = typer.Option(
        "--regex",
        "--engines",
        help="Engine flags to pass to pbd-toolkit scan (default: --regex)",
    ),
    git_dir: str = typer.Option(
        ".",
        "--git-dir",
        help="Root of the git repository (default: current directory)",
    ),
    force: bool = typer.Option(
        False, "--force", help="Overwrite an existing hook without confirmation"
    ),
) -> None:
    """Install a git hook that scans staged files for PII before committing.

    The hook runs ``pbd-toolkit scan`` on all staged files. The commit is
    blocked if any PII findings exceed severity MEDIUM.

    [bold]Examples:[/bold]

        pbd-toolkit install-hook

        pbd-toolkit install-hook --engines "--regex --ner" --force
    """
    import stat

    hooks_dir = os.path.join(git_dir, ".git", "hooks")
    if not os.path.isdir(hooks_dir):
        typer.echo(
            f"Error: .git/hooks directory not found in '{git_dir}'. "
            "Make sure you are inside a git repository.",
            err=True,
        )
        raise typer.Exit(code=constants.EXIT_INVALID_ARGUMENTS)

    hook_path = os.path.join(hooks_dir, hook_type)

    if os.path.exists(hook_path) and not force:
        overwrite = typer.confirm(
            f"Hook already exists at '{hook_path}'. Overwrite?", default=False
        )
        if not overwrite:
            typer.echo("Aborted.")
            raise typer.Exit()

    hook_script = f"""#!/bin/sh
# pbd-toolkit {hook_type} hook – auto-generated
# Scans staged files for PII. Blocks commit if HIGH/CRITICAL findings exist.

set -e

STAGED_FILES=$(git diff --cached --name-only --diff-filter=ACM)
if [ -z "$STAGED_FILES" ]; then
    exit 0
fi

TMPDIR=$(mktemp -d)
trap "rm -rf $TMPDIR" EXIT

echo "$STAGED_FILES" | while IFS= read -r f; do
    [ -f "$f" ] && cp --parents "$f" "$TMPDIR/" 2>/dev/null || true
done

pbd-toolkit scan "$TMPDIR" {engines} \\
    --format json --outname pbd_hook_check --output-dir "$TMPDIR/out/" --quiet 2>/dev/null || true

FINDINGS=$(find "$TMPDIR/out/" -name "*.json" | head -1)
if [ -n "$FINDINGS" ]; then
    CRITICAL=$(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(sum(1 for f in d.get('findings',[]) if f.get('severity') in ('CRITICAL','HIGH')))" "$FINDINGS" 2>/dev/null || echo 0)
    if [ "$CRITICAL" -gt 0 ]; then
        echo ""
        echo "pbd-toolkit: $CRITICAL HIGH/CRITICAL PII finding(s) detected in staged files."
        echo "Run: pbd-toolkit scan . {engines} --format json"
        echo "to review findings before committing."
        echo ""
        exit 1
    fi
fi

exit 0
"""

    with open(hook_path, "w", encoding="utf-8") as f:
        f.write(hook_script)

    # Make executable
    current_mode = os.stat(hook_path).st_mode
    os.chmod(hook_path, current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    typer.echo(f"Git {hook_type} hook installed at: {hook_path}")
    typer.echo(
        "The hook will scan staged files with: "
        f"pbd-toolkit scan <staged_files> {engines}"
    )


@app.command("test-pattern")
def test_pattern(
    text: str | None = typer.Option(
        None,
        "--text",
        "-t",
        help="Text to scan for PII. If omitted, reads from stdin.",
    ),
    regex: bool = typer.Option(
        True, "--regex/--no-regex", help="Use regex engine (default: on)"
    ),
    ner: bool = typer.Option(False, "--ner", help="Use GLiNER NER engine"),
    show_all: bool = typer.Option(
        False,
        "--show-all",
        help="Show all matches including low-confidence ones",
    ),
    output_format: str = typer.Option(
        "human",
        "--format",
        help="Output format: 'human' (default) or 'json'",
        case_sensitive=False,
    ),
) -> None:
    """Test detection engines against a text snippet without scanning files.

    Useful for verifying that your patterns, whitelists, and engine settings
    produce the expected results before running a full scan.

    [bold]Examples:[/bold]

        pbd-toolkit test-pattern --text "Call me at +49 30 123456"

        echo "IBAN: DE89370400440532013000" | pbd-toolkit test-pattern

        pbd-toolkit test-pattern --text "anna.schmidt@example.com" --format json
    """
    import json as _json
    import sys

    if text is None:
        if sys.stdin.isatty():
            typer.echo(
                "Reading from stdin … (pass --text to provide text directly)",
                err=True,
            )
        text = sys.stdin.read()

    if not text.strip():
        typer.echo("Error: no input text provided.", err=True)
        raise typer.Exit(code=constants.EXIT_INVALID_ARGUMENTS)

    if not regex and not ner:
        typer.echo(
            "Error: at least one engine must be enabled (--regex or --ner).",
            err=True,
        )
        raise typer.Exit(code=constants.EXIT_INVALID_ARGUMENTS)

    from core.matches import PiiMatchContainer

    container = PiiMatchContainer()

    if regex:
        import logging

        from core.config import Config
        from core.engines.regex_engine import RegexEngine

        cfg_obj = Config(
            use_regex=True, verbose=False, logger=logging.getLogger(__name__)
        )
        cfg_obj._load_regex_pattern()
        engine = RegexEngine(cfg_obj)
        if engine.is_available():
            results = engine.detect(text)
            container.add_detection_results(results, "<test-input>")

    if ner:
        try:
            from core.engines.gliner_engine import GLiNEREngine

            cfg_obj = type(
                "C", (), {"ner_threshold": 0.3, "ner_labels": [], "verbose": False}
            )()
            engine_ner = GLiNEREngine(cfg_obj)
            if engine_ner.is_available():
                results_ner = engine_ner.detect(text)
                container.add_detection_results(results_ner, "<test-input>")
        except ImportError:
            typer.echo(
                "Warning: GLiNER not installed (pip install 'pbd-toolkit[gliner]')",
                err=True,
            )

    matches = container.pii_matches
    if not show_all:
        matches = [
            m for m in matches if (m.ner_score or 0) >= 0.3 or m.engine == "regex"
        ]

    if output_format.lower() == "json":
        typer.echo(
            _json.dumps(
                [
                    {
                        "text": m.text,
                        "type": m.type,
                        "engine": m.engine,
                        "score": m.ner_score,
                        "severity": m.severity,
                    }
                    for m in matches
                ],
                indent=2,
                ensure_ascii=False,
            )
        )
    else:
        if not matches:
            typer.echo("No PII detected in the provided text.")
        else:
            typer.echo(f"\nFound {len(matches)} PII finding(s):\n")
            sep = "─" * 60
            typer.echo(sep)
            for m in matches:
                score_str = f"  score={m.ner_score:.3f}" if m.ner_score else ""
                typer.echo(
                    f"  [{m.severity or '?'}] {m.type}  (engine: {m.engine}{score_str})"
                )
                typer.echo(f"  → {m.text!r}")
                typer.echo(sep)


@app.command("export-config")
def export_config(
    output_path: str | None = typer.Argument(
        None,
        help="Output file path (default: stdout). Use .yaml or .json extension.",
    ),
    output_format: str = typer.Option(
        "yaml",
        "--format",
        help="Output format: 'yaml' (default) or 'json'",
        case_sensitive=False,
    ),
    config: Path | None = typer.Option(
        None,
        "--config",
        help="Base config file to export (optional, uses defaults otherwise)",
    ),
) -> None:
    """Export the current (default) configuration to a reusable YAML or JSON file.

    The exported file can be used with ``pbd-toolkit scan --config <file>`` to
    reproduce identical scan settings across teams and CI pipelines.

    [bold]Examples:[/bold]

        pbd-toolkit export-config                          # print defaults to stdout

        pbd-toolkit export-config my-scan.yaml            # save to file

        pbd-toolkit export-config --format json > cfg.json
    """
    import dataclasses
    import json as _json

    from core.config import Config

    # Build a default Config (optionally merged from file)
    cfg = Config()
    if config is not None:
        try:
            from core.config_loader import ConfigLoader

            file_data = ConfigLoader.load_config(config)
            for key, value in file_data.items():
                if hasattr(cfg, key):
                    setattr(cfg, key, value)
        except Exception as exc:
            typer.echo(f"Warning: could not load config file: {exc}", err=True)

    # Serialise sub-configs to nested dicts, skipping non-serialisable fields
    def _to_dict(dc_instance) -> dict:
        result = {}
        for f in dataclasses.fields(dc_instance):
            val = getattr(dc_instance, f.name)
            if isinstance(val, (str, int, float, bool, list, dict, type(None))):
                result[f.name] = val
        return result

    export_data = {
        "scan": _to_dict(cfg.scan),
        "engine": _to_dict(cfg.engine),
        "output": _to_dict(cfg.output),
    }

    if output_format.lower() == "json":
        serialized = _json.dumps(export_data, indent=2, ensure_ascii=False)
    else:
        try:
            import yaml as _yaml

            serialized = _yaml.dump(export_data, allow_unicode=True, sort_keys=False)
        except ImportError:
            # Fallback: manual YAML-like output without pyyaml
            serialized = _json.dumps(export_data, indent=2, ensure_ascii=False)
            typer.echo(
                "Warning: PyYAML not installed, falling back to JSON format.",
                err=True,
            )

    if output_path:
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(serialized + "\n")
            typer.echo(f"Configuration exported to: {output_path}")
        except OSError as exc:
            typer.echo(f"Error writing config: {exc}", err=True)
            raise typer.Exit(code=constants.EXIT_GENERAL_ERROR)
    else:
        typer.echo(serialized)


def cli() -> None:
    """Entry point for CLI - calls Typer app."""
    app()


if __name__ == "__main__":
    cli()
