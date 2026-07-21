"""Configuration management for the pbD Toolkit.

Design rationale – sub-config grouping
---------------------------------------
``Config`` is the single dependency-injection object passed through the entire call
stack (CLI → scanner → processor → engines → writers).  To keep it manageable it
groups related fields into four typed sub-configs, each the sole owner of its fields:

  ``scan``    – file discovery and safety limits (paths, timeouts, size caps, excludes)
  ``engine``  – detection engine selection and tuning (API URLs, models, thresholds, NER)
  ``output``  – result formatting and streaming (output path, deduplication, chunking)
  ``runtime`` – cross-cutting services (logger, CSV handles, verbosity, i18n)

Every field lives in exactly one sub-config. For backward compatibility with the
~200 call sites written before this split, all fields remain readable/writable at
the top level too (``config.max_file_size_mb`` as well as ``config.scan.max_file_size_mb``)
via properties attached to ``Config`` (one per delegated field, generated below the
class body), which transparently proxy to the owning sub-config. There is no
duplicate storage and no separate "sync" step: the top-level name and the
sub-config attribute are the same value, so mutating either one is always immediately
visible through the other. New code — especially component constructors migrating to
depend on a single scoped config — should prefer ``config.scan``/``config.engine``/
``config.output``/``config.runtime`` directly.

Configuration precedence (highest → lowest):
  1. CLI flags  – explicit user intent; never overridden
  2. Config file (--config) – operator defaults for recurring scans
  3. Environment variables (PBD_TOOLKIT_*, PBD_LOG_LEVEL, PBD_OUTPUT_DIR)
  4. Hardcoded defaults below – safe for first-run without any configuration
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import _csv

    from gliner import GLiNER

from core import constants
from core.resources import load_config_types


@dataclass
class NerStats:
    """Statistics for NER processing."""

    total_chunks_processed: int = 0
    total_entities_found: int = 0
    total_processing_time: float = 0.0
    entities_by_type: dict[str, int] = field(default_factory=dict)
    errors: int = 0


@dataclass
class ScanConfig:
    """File discovery and safety-limit parameters for a scan run."""

    path: str = ""
    whitelist_path: str | None = None
    stop_count: int | None = None
    use_magic_detection: bool = False
    magic_detection_fallback: bool = True
    use_incremental: bool = False
    cache_path: str | None = None
    # 500 MB: prevents OOM on memory-constrained systems while still covering
    # large database dumps and mail archives common in GDPR audit scenarios.
    # Can be raised via config file for environments with sufficient RAM.
    max_file_size_mb: float = 500.0
    # 5-minute hard timeout per file prevents infinite loops caused by
    # malformed archives (e.g. recursive ZIPs, cyclic XML includes, corrupt PDFs).
    max_processing_time_seconds: int = 300
    # Backpressure cap: limits the number of in-flight async file callbacks so
    # that the scanner does not exhaust OS file descriptors on deep directory trees.
    max_pending_futures: int = 512
    # Glob patterns for files/directories to skip during scanning.
    exclude_patterns: list[str] = field(default_factory=list)
    # Tuning limit for the compiled whitelist regex (configurable via settings file).
    max_whitelist_regex_len: int = 500


@dataclass
class EngineConfig:
    """Configuration related to detection engines."""

    # Engine flags
    use_regex: bool = False
    use_ner: bool = False
    use_spacy_ner: bool = False
    use_ollama: bool = False
    use_openai_compatible: bool = False
    use_multimodal: bool = False
    use_pydantic_ai: bool = False

    # spaCy
    spacy_model_name: str = "de_core_news_lg"

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    ollama_timeout: int = 30  # seconds; generous for local inference on CPU

    # OpenAI-compatible
    openai_api_base: str = "https://api.openai.com/v1"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    openai_timeout: int = 30  # seconds; network API; 30 s is P99 for most providers

    # Multimodal gets 2× the text timeout because image payloads are sent as
    # base64-encoded data URLs, which are substantially larger than text prompts
    # and cause higher network and server processing latency.
    multimodal_api_base: str | None = None
    multimodal_api_key: str | None = None
    multimodal_model: str = "gpt-4-vision-preview"
    multimodal_timeout: int = 60

    # PydanticAI unified engine
    pydantic_ai_provider: str = "openai"
    pydantic_ai_model: str | None = None
    pydantic_ai_api_key: str | None = None
    pydantic_ai_base_url: str | None = None

    # LLM retry
    llm_max_retries: int = 3
    llm_retry_base_delay: float = 1.0

    # Vector search
    use_vector_search: bool = False
    use_vector_triage: bool = False
    vector_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    vector_threshold: float = 0.75
    vector_save_index: str | None = None
    vector_load_index: str | None = None
    vector_custom_exemplars: str | None = None

    # Concurrency
    engine_concurrency_limits: dict[str, int] = field(default_factory=dict)

    # Regex engine: compiled combined pattern (built from config_types.json at load time)
    regex_pattern: re.Pattern | None = field(default=None)

    # NER (GLiNER) engine state
    ner_model: GLiNER | None = field(default=None)
    ner_labels: list[str] = field(default_factory=list)
    ner_threshold: float = field(default=constants.NER_THRESHOLD)
    # Optional per-label confidence thresholds for GLiNER, keyed by the GLiNER label
    # (e.g. {"Person's Name": 0.7, "Health Data": 0.4}).  Labels not listed fall back
    # to ner_threshold.  Lets operators tighten high-precision categories while keeping
    # recall on harder ones.
    ner_label_thresholds: dict = field(default_factory=dict)
    ner_stats: NerStats = field(default_factory=NerStats)

    # Ollama NER label configuration
    ollama_labels: list[dict] = field(default_factory=list)


@dataclass
class OutputConfig:
    """Configuration related to output and processing behaviour."""

    outname: str | None = None
    enable_deduplication: bool = False
    min_confidence: float = 0.0
    text_chunk_size: int = 0
    text_chunk_overlap: int = 200
    context_chars: int = 0
    analytics_enabled: bool = False
    analytics_db_path: str = ".pbd_analytics.db"
    # Output severity filter: only include findings at or above this level in output
    min_severity: str | None = None
    # CI/CD: exit with non-zero code when findings at or above this level are present
    fail_on_severity: str | None = None
    # Tuning limit for deduplication (configurable via settings file)
    dedup_max_entries: int = 500_000


@dataclass
class RuntimeConfig:
    """Cross-cutting runtime services: logging, I/O handles, verbosity, i18n.

    These aren't scan/engine/output concerns in their own right — they're
    infrastructure threaded through every layer of the call stack.
    """

    logger: logging.Logger | None = field(default=None)
    csv_writer: _csv.Writer | None = field(default=None)
    csv_file_handle: object | None = field(default=None)
    verbose: bool = False
    # Translation function
    _: Callable[[str], str] = field(default=lambda x: x)


_SUB_CONFIG_TYPES: dict[str, type] = {
    "scan": ScanConfig,
    "engine": EngineConfig,
    "output": OutputConfig,
    "runtime": RuntimeConfig,
}


def _build_field_groups() -> dict[str, tuple[str, ...]]:
    """Derive sub-config field mappings from dataclass introspection.

    Adding a new field only requires adding it to the owning sub-config
    dataclass — the top-level ``Config`` delegation picks it up automatically.
    """
    import dataclasses as _dc

    return {
        group: tuple(f.name for f in _dc.fields(cls))
        for group, cls in _SUB_CONFIG_TYPES.items()
    }


_FIELD_GROUPS = _build_field_groups()

# Reverse mapping: top-level attribute name -> owning sub-config group name.
_ATTR_TO_GROUP: dict[str, str] = {
    name: group for group, names in _FIELD_GROUPS.items() for name in names
}


class Config:
    """Configuration object for pbD Toolkit.

    This class centralizes all configuration and dependencies, enabling
    dependency injection and better testability.

    Every field is owned by exactly one of the ``scan``/``engine``/``output``/
    ``runtime`` sub-configs (see the module docstring). There is no separate
    storage for the top-level name: ``config.max_file_size_mb`` and
    ``config.scan.max_file_size_mb`` are the same value. Each delegated name is
    a real ``property`` on this class (attached below the class body) whose
    getter/setter proxy to the owning sub-config — deliberately *not*
    ``__getattr__``/``__setattr__`` interception, because ``unittest.mock.Mock(spec=Config)``
    (used throughout the test suite) validates attribute names against
    ``dir(Config)``, which only sees real class attributes. Construct it either
    the old flattened way (``Config(path=..., use_regex=..., logger=...)``, for
    ~200 existing call sites) or by passing pre-built sub-config objects
    (``Config(scan=ScanConfig(...), engine=EngineConfig(...))``).
    """

    if TYPE_CHECKING:
        # Static mirror of the properties attached dynamically below the class
        # body, purely so mypy resolves `config.<field>` access. Never executes
        # at runtime (TYPE_CHECKING is False), so it has no effect on `dir()` /
        # `Mock(spec=Config)`. Keep in sync with ScanConfig/EngineConfig/
        # OutputConfig/RuntimeConfig — a mismatch here only breaks type-checking,
        # never runtime behaviour, since the real properties are what's used.

        # ScanConfig
        path: str
        whitelist_path: str | None
        stop_count: int | None
        use_magic_detection: bool
        magic_detection_fallback: bool
        use_incremental: bool
        cache_path: str | None
        max_file_size_mb: float
        max_processing_time_seconds: int
        max_pending_futures: int
        exclude_patterns: list[str]
        max_whitelist_regex_len: int

        # EngineConfig
        use_regex: bool
        use_ner: bool
        use_spacy_ner: bool
        use_ollama: bool
        use_openai_compatible: bool
        use_multimodal: bool
        use_pydantic_ai: bool
        spacy_model_name: str
        ollama_base_url: str
        ollama_model: str
        ollama_timeout: int
        openai_api_base: str
        openai_api_key: str | None
        openai_model: str
        openai_timeout: int
        multimodal_api_base: str | None
        multimodal_api_key: str | None
        multimodal_model: str
        multimodal_timeout: int
        pydantic_ai_provider: str
        pydantic_ai_model: str | None
        pydantic_ai_api_key: str | None
        pydantic_ai_base_url: str | None
        llm_max_retries: int
        llm_retry_base_delay: float
        use_vector_search: bool
        use_vector_triage: bool
        vector_model: str
        vector_threshold: float
        vector_save_index: str | None
        vector_load_index: str | None
        vector_custom_exemplars: str | None
        engine_concurrency_limits: dict[str, int]
        regex_pattern: re.Pattern | None
        ner_model: GLiNER | None
        ner_labels: list[str]
        ner_threshold: float
        ner_label_thresholds: dict
        ner_stats: NerStats
        ollama_labels: list[dict]

        # OutputConfig
        outname: str | None
        enable_deduplication: bool
        min_confidence: float
        text_chunk_size: int
        text_chunk_overlap: int
        context_chars: int
        analytics_enabled: bool
        analytics_db_path: str
        min_severity: str | None
        fail_on_severity: str | None
        dedup_max_entries: int

        # RuntimeConfig
        logger: logging.Logger | None
        csv_writer: _csv.Writer | None
        csv_file_handle: object | None
        verbose: bool
        _: Callable[[str], str]

    def __init__(
        self,
        *,
        scan: ScanConfig | None = None,
        engine: EngineConfig | None = None,
        output: OutputConfig | None = None,
        runtime: RuntimeConfig | None = None,
        **flat_kwargs: object,
    ) -> None:
        """Create a Config from either sub-config objects or flattened kwargs.

        Args:
            scan: Pre-built ScanConfig. Mutually exclusive with flattened scan fields.
            engine: Pre-built EngineConfig. Mutually exclusive with flattened engine fields.
            output: Pre-built OutputConfig. Mutually exclusive with flattened output fields.
            runtime: Pre-built RuntimeConfig. Mutually exclusive with flattened runtime fields.
            **flat_kwargs: Backward-compatible flattened fields (e.g. ``path=``,
                ``use_regex=``, ``logger=``), routed to the sub-config that owns
                each name.

        Raises:
            TypeError: If a flattened kwarg name isn't owned by any sub-config,
                or if both a pre-built sub-config and its flattened fields are given.
        """
        grouped_kwargs: dict[str, dict[str, object]] = {
            "scan": {},
            "engine": {},
            "output": {},
            "runtime": {},
        }
        for name, value in flat_kwargs.items():
            group = _ATTR_TO_GROUP.get(name)
            if group is None:
                raise TypeError(f"Config() got an unexpected keyword argument {name!r}")
            grouped_kwargs[group][name] = value

        provided = {
            "scan": scan,
            "engine": engine,
            "output": output,
            "runtime": runtime,
        }
        for group, sub in provided.items():
            if sub is not None and grouped_kwargs[group]:
                raise TypeError(
                    f"Config() got both {group}= and flattened {group} field(s) "
                    f"{tuple(grouped_kwargs[group])!r}; pass one or the other"
                )

        # The flattened kwargs are heterogeneous by design (any mix of the four
        # sub-configs' fields keyed by name); correctness is enforced at runtime
        # by the _ATTR_TO_GROUP partitioning above, not statically checkable here.
        self.scan = (
            scan if scan is not None else ScanConfig(**grouped_kwargs["scan"])  # type: ignore[arg-type]
        )
        self.engine = (
            engine if engine is not None else EngineConfig(**grouped_kwargs["engine"])  # type: ignore[arg-type]
        )
        self.output = (
            output if output is not None else OutputConfig(**grouped_kwargs["output"])  # type: ignore[arg-type]
        )
        self.runtime = (
            runtime
            if runtime is not None
            else RuntimeConfig(**grouped_kwargs["runtime"])  # type: ignore[arg-type]
        )

        if self.runtime._ is None or not callable(self.runtime._):
            # Fallback if translation not set (e.g. explicit _=None was passed).
            self.runtime._ = lambda x: x

    def __repr__(self) -> str:
        return (
            f"Config(scan={self.scan!r}, engine={self.engine!r}, "
            f"output={self.output!r}, runtime={self.runtime!r})"
        )

    def validate_path(self) -> tuple[bool, str | None]:
        """Validate the search path.

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not self.path:
            return False, self._("--path parameter cannot be empty")

        if not os.path.exists(self.path):
            return False, self._("Path does not exist: {}").format(self.path)

        if not os.path.isdir(self.path):
            return False, self._("Path is not a directory: {}").format(self.path)

        if not os.access(self.path, os.R_OK):
            return False, self._("Path is not readable: {}").format(self.path)

        return True, None

    def validate_file_path(self, file_path: str) -> tuple[bool, str | None]:
        """Validate file path and check for path traversal.

        Args:
            file_path: Path to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Resolve to absolute paths to prevent path traversal
            real_base = os.path.realpath(self.path)
            real_file = os.path.realpath(file_path)

            # Check if file is within base directory
            if not real_file.startswith(real_base + os.sep) and real_file != real_base:
                return False, "Path traversal attempt detected"

            # Check file size limit
            if os.path.isfile(file_path):
                file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
                if file_size_mb > self.max_file_size_mb:
                    return (
                        False,
                        f"File too large: {file_size_mb:.2f} MB (max: {self.max_file_size_mb} MB)",
                    )

            return True, None
        except (OSError, ValueError) as e:
            return False, f"Path validation error: {str(e)}"

    @classmethod
    def from_args(
        cls,
        args: argparse.Namespace,
        logger: logging.Logger,
        csv_writer: _csv.Writer | None,
        csv_file_handle: object | None,
        translate_func: Callable[[str], str],
    ) -> Config:
        """Create Config from command line arguments.

        Args:
            args: Parsed command line arguments
            logger: Logger instance
            csv_writer: CSV writer instance
            csv_file_handle: CSV file handle
            translate_func: Translation function

        Returns:
            Config instance
        """
        config = cls(
            path=args.path or "",
            use_regex=args.regex or False,
            use_ner=args.ner or False,
            verbose=args.verbose or False,
            outname=args.outname,
            whitelist_path=args.whitelist,
            stop_count=args.stop_count,
            use_spacy_ner=getattr(args, "spacy_ner", False),
            use_ollama=getattr(args, "ollama", False),
            use_openai_compatible=getattr(args, "openai_compatible", False),
            use_multimodal=getattr(args, "multimodal", False),
            use_pydantic_ai=getattr(args, "pydantic_ai", False),
            use_magic_detection=getattr(args, "use_magic_detection", False),
            magic_detection_fallback=getattr(args, "magic_fallback", True),
            use_vector_search=getattr(args, "vector_search", False),
            use_vector_triage=getattr(args, "vector_triage", False),
            logger=logger,
            csv_writer=csv_writer,
            csv_file_handle=csv_file_handle,
            _=translate_func,
        )

        # Load runtime settings from config_types.json (best-effort).
        config._load_runtime_settings()

        # Set engine-specific configuration from args
        if hasattr(args, "spacy_model"):
            config.spacy_model_name = args.spacy_model
        if hasattr(args, "ollama_url"):
            config.ollama_base_url = args.ollama_url
        if hasattr(args, "ollama_model"):
            config.ollama_model = args.ollama_model
        if hasattr(args, "openai_api_base"):
            config.openai_api_base = args.openai_api_base
        if hasattr(args, "openai_api_key"):
            config.openai_api_key = args.openai_api_key
        if hasattr(args, "openai_model"):
            config.openai_model = args.openai_model

        # Multimodal configuration
        if hasattr(args, "multimodal_api_base"):
            config.multimodal_api_base = args.multimodal_api_base
        elif config.use_multimodal:
            # Default to openai_api_base if not specified
            config.multimodal_api_base = config.openai_api_base
        if hasattr(args, "multimodal_api_key"):
            config.multimodal_api_key = args.multimodal_api_key
        elif config.use_multimodal:
            # Default to openai_api_key if not specified
            config.multimodal_api_key = config.openai_api_key
        if hasattr(args, "multimodal_model"):
            config.multimodal_model = args.multimodal_model
        if hasattr(args, "multimodal_timeout"):
            config.multimodal_timeout = args.multimodal_timeout

        # Vector search configuration
        if hasattr(args, "vector_model"):
            config.vector_model = args.vector_model
        if hasattr(args, "vector_threshold"):
            config.vector_threshold = args.vector_threshold
        if hasattr(args, "vector_save_index") and args.vector_save_index:
            config.vector_save_index = args.vector_save_index
        if hasattr(args, "vector_load_index") and args.vector_load_index:
            config.vector_load_index = args.vector_load_index
        if hasattr(args, "vector_custom_exemplars") and args.vector_custom_exemplars:
            config.vector_custom_exemplars = args.vector_custom_exemplars

        # PydanticAI configuration
        if hasattr(args, "pydantic_ai_provider"):
            config.pydantic_ai_provider = args.pydantic_ai_provider
        if hasattr(args, "pydantic_ai_model"):
            config.pydantic_ai_model = args.pydantic_ai_model
        if hasattr(args, "pydantic_ai_api_key"):
            config.pydantic_ai_api_key = args.pydantic_ai_api_key
        if hasattr(args, "pydantic_ai_base_url"):
            config.pydantic_ai_base_url = args.pydantic_ai_base_url

        # Load regex pattern
        config._load_regex_pattern()

        # Load NER model if needed
        if config.use_ner:
            config._load_ner_model()

        return config

    def _load_runtime_settings(self) -> None:
        """Load runtime settings from config_types.json.

        This is best-effort: missing keys or malformed values should not break scans.
        """
        try:
            cfg = load_config_types()
        except FileNotFoundError:
            self.logger.debug("config_types.json not found, skipping runtime settings")
            return
        except Exception as exc:
            self.logger.warning(
                "Failed to load config_types.json for runtime settings: %s", exc
            )
            return

        settings = cfg.get("settings", {}) if isinstance(cfg, dict) else {}
        if not isinstance(settings, dict):
            return

        max_file_size_mb = settings.get("max_file_size_mb")
        if isinstance(max_file_size_mb, (int, float)) and max_file_size_mb > 0:
            self.max_file_size_mb = float(max_file_size_mb)

        max_processing_time_seconds = settings.get("max_processing_time_seconds")
        if (
            isinstance(max_processing_time_seconds, int)
            and max_processing_time_seconds > 0
        ):
            self.max_processing_time_seconds = int(max_processing_time_seconds)

        max_pending_futures = settings.get("max_pending_futures")
        if isinstance(max_pending_futures, int) and max_pending_futures > 0:
            self.max_pending_futures = int(max_pending_futures)

        limits = settings.get("engine_concurrency_limits")
        if isinstance(limits, dict):
            cleaned: dict[str, int] = {}
            for k, v in limits.items():
                if isinstance(k, str) and isinstance(v, int) and v >= 1:
                    cleaned[k] = v
            self.engine_concurrency_limits = cleaned

    def _load_regex_pattern(self) -> None:
        """Load and compile regex pattern from config file."""
        try:
            config_data = load_config_types()
            regex_entries = config_data.get("regex", [])
            # Validate positional mapping contract: the combined regex is compiled as a
            # sequence of capturing groups, and match group index (0-based) is used to
            # map back to config entries. This only works reliably when the configured
            # regex_compiled_pos values are unique and match the entry order.
            if self.logger and regex_entries:
                seen: set[int] = set()
                invalid_pos = False
                for i, entry in enumerate(regex_entries):
                    pos = entry.get("regex_compiled_pos")
                    if not isinstance(pos, int):
                        invalid_pos = True
                        continue
                    if pos in seen:
                        invalid_pos = True
                    seen.add(pos)
                    if pos != i:
                        # This is a soft warning: the mapping logic in matches/engines
                        # relies on pos==index today.
                        self.logger.warning(
                            "Regex config mapping may be inconsistent: "
                            f"entry '{entry.get('label', '<unknown>')}' has regex_compiled_pos={pos} "
                            f"but appears at index {i}."
                        )
                if invalid_pos:
                    self.logger.warning(
                        "Regex config contains invalid or duplicate 'regex_compiled_pos' values. "
                        "Match type mapping may be incorrect."
                    )
            regex_supported = [
                r"{}".format(entry["expression"]) for entry in regex_entries
            ]

            if regex_supported:
                rxstr_all = "(" + ")|(".join(regex_supported) + ")"
                # Make regex detection robust to case variants by default.
                self.regex_pattern = re.compile(rxstr_all, flags=re.IGNORECASE)
        except (FileNotFoundError, json.JSONDecodeError, KeyError, re.error) as e:
            self.logger.warning(f"Failed to load regex pattern: {e}")
            self.regex_pattern = None

    def _load_ner_model(self) -> None:
        """Load NER model and labels.

        Loads the GLiNER model from HuggingFace and configures labels and threshold
        from config_types.json. Handles various error cases with specific error messages.
        Automatically detects and uses GPU if available (unless FORCE_CPU is True).
        """
        try:
            self.logger.info(self._("Loading NER model..."))

            # Disable telemetry for privacy
            os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
            os.environ.setdefault("TORCH_DISABLE_TELEMETRY", "1")

            # Check for GPU availability
            device = "cpu"
            if not constants.FORCE_CPU:
                try:
                    import torch

                    if torch.cuda.is_available():
                        device = "cuda"
                        gpu_name = torch.cuda.get_device_name(0)
                        self.logger.info(self._("GPU detected: {}").format(gpu_name))
                    else:
                        self.logger.info(self._("Using CPU for NER processing"))
                except ImportError:
                    self.logger.debug("PyTorch not available, using CPU")
                except Exception as e:
                    self.logger.warning(
                        self._("GPU detection failed, using CPU: {}").format(e)
                    )
            else:
                self.logger.info(
                    self._("CPU forced for NER processing (FORCE_CPU=True)")
                )

            from gliner import GLiNER

            self.ner_model = GLiNER.from_pretrained(constants.NER_MODEL_NAME)

            # Move model to device if supported
            if device == "cuda" and hasattr(self.ner_model, "to"):
                try:
                    self.ner_model = self.ner_model.to(device)
                    self.logger.info(self._("NER model moved to GPU"))
                except Exception as e:
                    self.logger.warning(
                        self._("Failed to move model to GPU, using CPU: {}").format(e)
                    )

            self.logger.info(
                self._("NER model loaded: {}").format(constants.NER_MODEL_NAME)
            )

            config_data = load_config_types()

            # Load NER labels
            ner_config = config_data.get("ai-ner", [])
            self.ner_labels = [c["term"] for c in ner_config]

            # Load Ollama labels
            ollama_config = config_data.get("ollama-ner", [])
            # If no Ollama specific config, fallback to NER labels structure but adapted
            if not ollama_config:
                self.ollama_labels = [
                    {"term": c["term"], "description": c["term"]} for c in ner_config
                ]
            else:
                self.ollama_labels = ollama_config

            if not self.ner_labels:
                self.logger.warning(self._("No NER labels configured"))

            # Load threshold from config, fallback to constant
            settings = config_data.get("settings", {})
            self.ner_threshold = settings.get("ner_threshold", constants.NER_THRESHOLD)
            # Optional per-label thresholds (keyed by GLiNER label) for finer control.
            _label_thresholds = settings.get("ner_label_thresholds", {})
            if isinstance(_label_thresholds, dict):
                self.ner_label_thresholds = {
                    str(k): float(v) for k, v in _label_thresholds.items()
                }

            if self.verbose:
                self.logger.debug(f"NER threshold: {self.ner_threshold}")
                if self.ner_label_thresholds:
                    self.logger.debug(
                        f"NER per-label thresholds: {self.ner_label_thresholds}"
                    )
                self.logger.debug(f"NER labels: {self.ner_labels}")

            # Warm-up: First call to initialize model (reduces latency on first real use)
            if self.ner_model and self.ner_labels:
                try:
                    dummy_text = "This is a test sentence for model warm-up."
                    # Use first label for warm-up to minimize overhead
                    warmup_labels = self.ner_labels[:1] if self.ner_labels else []
                    if warmup_labels:
                        self.ner_model.predict_entities(
                            dummy_text, warmup_labels, threshold=self.ner_threshold
                        )
                        if self.verbose:
                            self.logger.debug("NER model warmed up")
                except Exception as e:
                    # Warm-up failure is not critical, but users should know
                    self.logger.warning(f"NER warm-up failed (non-critical): {e}")

        except FileNotFoundError as e:
            error_msg = (
                self._("NER model not found. Please download it first:\n")
                + f"  hf download {constants.NER_MODEL_NAME}\n"
                + self._("Original error: {}").format(str(e))
            )
            self.logger.error(error_msg)
            raise RuntimeError(error_msg) from e
        except ImportError as e:
            error_msg = (
                self._("GLiNER library not installed. Install with:\n")
                + "  pip install gliner\n"
                + self._("Original error: {}").format(str(e))
            )
            self.logger.error(error_msg)
            raise RuntimeError(error_msg) from e
        except json.JSONDecodeError as e:
            error_msg = self._("Failed to parse configuration file: {}").format(
                "config_types.json"
            ) + f"\n{self._('Original error: {}')}".format(str(e))
            self.logger.error(error_msg)
            raise RuntimeError(error_msg) from e
        except Exception as e:
            error_msg = self._("Failed to load NER model: {}").format(str(e))
            self.logger.error(error_msg, exc_info=True)
            raise RuntimeError(error_msg) from e


def _make_delegated_property(name: str, group: str) -> property:
    """Build a property proxying attribute *name* to ``self.<group>.<name>``."""

    def getter(self: Config) -> object:
        return getattr(getattr(self, group), name)

    def setter(self: Config, value: object) -> None:
        setattr(getattr(self, group), name, value)

    getter.__name__ = name
    return property(getter, setter, doc=f"Proxy for ``{group}.{name}``.")


# Attach one property per sub-config field directly on the Config class so that
# every delegated name is a real class attribute: this keeps `dir(Config)` (and
# therefore `unittest.mock.Mock(spec=Config)`) accurate, and — because properties
# are data descriptors — guarantees the top-level name can never silently shadow
# or go stale relative to the owning sub-config's value.
for _name, _group in _ATTR_TO_GROUP.items():
    setattr(Config, _name, _make_delegated_property(_name, _group))
del _name, _group


def load_extended_config(config_file: str = constants.CONFIG_FILE) -> dict:
    """Load extended configuration from JSON file.

    Args:
        config_file: Path to configuration file

    Returns:
        Dictionary with configuration
    """
    try:
        if config_file == constants.CONFIG_FILE:
            config = load_config_types()
        else:
            with open(config_file) as f:
                config = json.load(f)

        # Set defaults for extended settings if not present
        if "settings" not in config:
            config["settings"] = {}

        settings = config["settings"]

        # Set defaults
        defaults = {
            "ner_threshold": constants.NER_THRESHOLD,
            "min_pdf_text_length": constants.MIN_PDF_TEXT_LENGTH,
            "max_file_size_mb": 500.0,
            "max_processing_time_seconds": 300,
            "supported_extensions": [".pdf", ".docx", ".html", ".txt"],
            "logging": {"level": "INFO", "format": "detailed"},
        }

        for key, value in defaults.items():
            if key not in settings:
                settings[key] = value

        return config
    except (FileNotFoundError, json.JSONDecodeError) as e:
        raise ValueError(f"Failed to load configuration: {e}")
