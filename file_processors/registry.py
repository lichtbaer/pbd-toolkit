"""File processor registry: automatic discovery and routing to format-specific processors.

Design rationale – dynamic registration vs. static import list
--------------------------------------------------------------
New file formats are added by creating a processor class and registering it in
``file_processors/__init__.py``.  The registry itself never needs to be modified.
This avoids the ``if ext == ".pdf": ... elif ext == ".docx": ...`` anti-pattern and
keeps the core scanner decoupled from individual format dependencies.

Registration order matters for priority: when multiple processors claim the same
extension (e.g. both a generic text processor and a specialised markdown processor
handle ``.md``), the first registered processor wins.  Specialised processors should
therefore be registered before generic fallbacks.

Extension caching
-----------------
``get_processor`` caches extension → processor mappings after the first lookup.
The cache is keyed on extension only (MIME type lookups bypass the cache) so that
magic-number-detected files are always re-dispatched to the full processor list.
The cache is cleared whenever a new processor is registered.

Registry lifecycle: default vs. isolated
-----------------------------------------
``FileProcessorRegistry``'s classmethods operate on process-global state populated
once at import time by ``file_processors/__init__.py``.  That default registry is
what the CLI (and, by extension, ``ScanRunner``) uses unless told otherwise, and its
import-time registration behavior is unchanged by the isolation support below.

For tests, plugin experiments, or long-running processes (the REST API) that must
not mutate — or be affected by mutations of — that global state, use an isolated
registry instead:

- ``FileProcessorRegistry.create_isolated()`` returns an empty
  :class:`IsolatedFileProcessorRegistry` that a test can populate independently;
  nothing registered on it is visible to any other test or to the default registry.
- ``FileProcessorRegistry.snapshot()`` returns an :class:`IsolatedFileProcessorRegistry`
  pre-populated with a **copy** of whatever is currently registered globally — the
  shape the REST API uses so that every scan in a process sees the same stable set of
  processors, independent of whatever the global registry looks like at call time.

Both registry classes expose the same instance/class methods (``register``,
``register_class``, ``get_processor``, ``get_all_processors``,
``get_supported_extensions``), so callers that accept "a registry" (e.g.
``FileScanner``, ``TextProcessor``) can be handed either the ``FileProcessorRegistry``
class itself or an isolated instance interchangeably.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from file_processors.base_processor import BaseFileProcessor

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _CanProcessMeta:
    """Cached metadata about a processor's `can_process` signature.

    Avoids calling `inspect.signature` in the per-file hot path.
    """

    positional_param_count: int


def _compute_can_process_meta(processor: BaseFileProcessor) -> _CanProcessMeta:
    """Compute `can_process` signature metadata once per processor."""
    try:
        import inspect

        sig = inspect.signature(processor.can_process)
        # Count positional params; clamp to [1..3].
        positional = [
            p
            for p in sig.parameters.values()
            if p.kind
            in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            )
        ]
        count = len(positional)
        if any(
            p.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
            for p in sig.parameters.values()
        ):
            count = 3
        count = max(1, min(3, count))
        return _CanProcessMeta(positional_param_count=count)
    except Exception as exc:
        # Conservative: assume the most flexible signature.
        _logger.debug(
            "Could not inspect can_process signature for %r: %s", processor, exc
        )
        return _CanProcessMeta(positional_param_count=3)


def _register_processor(
    processors: list[BaseFileProcessor],
    extension_cache: dict[str, BaseFileProcessor],
    can_process_meta: dict[BaseFileProcessor, _CanProcessMeta],
    processor: BaseFileProcessor,
) -> None:
    if processor not in processors:
        processors.append(processor)
        # Clear cache when new processor is registered
        extension_cache.clear()
        can_process_meta[processor] = _compute_can_process_meta(processor)


def _resolve_processor(
    processors: list[BaseFileProcessor],
    can_process_meta: dict[BaseFileProcessor, _CanProcessMeta],
    extension_cache: dict[str, BaseFileProcessor],
    extension: str,
    file_path: str = "",
    mime_type: str = "",
) -> BaseFileProcessor | None:
    # Check cache first (only for processors that don't need file_path or mime_type)
    if extension and extension in extension_cache and not mime_type:
        return extension_cache[extension]

    # Check each processor
    for processor in processors:
        meta = can_process_meta.get(processor)
        if meta is None:
            meta = _compute_can_process_meta(processor)
            can_process_meta[processor] = meta

        try:
            if meta.positional_param_count >= 3:
                if processor.can_process(extension, file_path, mime_type):
                    # Safe to cache only when MIME type is not involved.
                    if extension and not mime_type:
                        extension_cache[extension] = processor
                    return processor
            elif meta.positional_param_count == 2:
                if processor.can_process(extension, file_path):
                    # Don't cache: may depend on file_path.
                    return processor
            else:
                if processor.can_process(extension):
                    if extension and not mime_type:
                        extension_cache[extension] = processor
                    return processor
        except (TypeError, ValueError):
            continue

    return None


_COMMON_EXTENSIONS = [
    ".pdf",
    ".docx",
    ".html",
    ".htm",
    ".txt",
    ".csv",
    ".json",
    ".rtf",
    ".odt",
    ".xlsx",
    ".xls",
    ".xml",
    ".pptx",
    ".ppt",
    ".eml",
    ".msg",
    ".ods",
    ".yaml",
    ".yml",
    ".md",
]


def _list_supported_extensions(processors: list[BaseFileProcessor]) -> list[str]:
    extensions = []
    for processor in processors:
        # Try to determine supported extensions from processor
        # This is a heuristic - processors should ideally expose this
        if hasattr(processor, "can_process"):
            for ext in _COMMON_EXTENSIONS:
                if processor.can_process(ext):
                    if ext not in extensions:
                        extensions.append(ext)
    return sorted(extensions)


class FileProcessorRegistry:
    """Registry for file processors with automatic registration.

    Class-level state (``_processors``, ``_extension_cache``) is shared across all
    call sites without instantiation.  This is intentional: there is exactly one
    global processor list per Python process, matching the single-registry pattern,
    and it is what CLI scans use by default. See the module docstring for how to get
    an isolated registry instead (``create_isolated()`` / ``snapshot()``) when global
    state would be unsafe, e.g. in tests or a long-running API process.

    Thread safety: registration (``register``) is not thread-safe and is only called
    during module import (before any worker threads are spawned), so no lock is needed.
    ``get_processor`` reads are thread-safe because CPython's GIL protects list/dict
    reads, and the cache is only written when a new processor is first seen for an
    extension (which happens at most once per extension in practice).
    """

    _processors: list[BaseFileProcessor] = []
    _extension_cache: dict[str, BaseFileProcessor] = {}
    _initialized: bool = False
    _can_process_meta: dict[BaseFileProcessor, _CanProcessMeta] = {}

    @classmethod
    def register(cls, processor: BaseFileProcessor) -> None:
        """Register a file processor.

        Args:
            processor: Processor instance to register
        """
        _register_processor(
            cls._processors, cls._extension_cache, cls._can_process_meta, processor
        )

    @classmethod
    def register_class(cls, processor_class: type[BaseFileProcessor]) -> None:
        """Register a processor class (creates instance automatically).

        Args:
            processor_class: Processor class to register
        """
        cls.register(processor_class())

    @classmethod
    def get_processor(
        cls, extension: str, file_path: str = "", mime_type: str = ""
    ) -> BaseFileProcessor | None:
        """Get the appropriate processor for a file extension.

        Args:
            extension: File extension (e.g., '.pdf', '.docx')
            file_path: Full path to the file (optional, needed for some processors)
            mime_type: Detected MIME type (optional, for magic number detection)

        Returns:
            Appropriate processor instance or None if no processor available
        """
        return _resolve_processor(
            cls._processors,
            cls._can_process_meta,
            cls._extension_cache,
            extension,
            file_path,
            mime_type,
        )

    @classmethod
    def get_all_processors(cls) -> list[BaseFileProcessor]:
        """Get all registered processors.

        Returns:
            List of all registered processor instances
        """
        return cls._processors.copy()

    @classmethod
    def clear(cls) -> None:
        """Clear all registered processors (mainly for testing)."""
        cls._processors.clear()
        cls._extension_cache.clear()
        cls._initialized = False
        cls._can_process_meta.clear()

    @classmethod
    def get_supported_extensions(cls) -> list[str]:
        """Get list of all supported file extensions.

        Returns:
            List of supported extensions (e.g., ['.pdf', '.docx', ...])
        """
        return _list_supported_extensions(cls._processors)

    @classmethod
    def create_isolated(cls) -> IsolatedFileProcessorRegistry:
        """Create a new, empty registry that never touches global state.

        Use this in tests or plugin experiments that need a clean processor set
        without racing other tests or mutating the process-wide default registry.
        """
        return IsolatedFileProcessorRegistry()

    @classmethod
    def snapshot(cls) -> IsolatedFileProcessorRegistry:
        """Create an isolated registry pre-populated from the current global state.

        Intended for long-running processes (the REST API) that want a stable
        processor set for the lifetime of a service instance, decoupled from
        whatever else might register or ``clear()`` the global registry at runtime.
        """
        isolated = IsolatedFileProcessorRegistry()
        for processor in cls._processors:
            isolated.register(processor)
        return isolated


class IsolatedFileProcessorRegistry:
    """An isolated, instance-scoped counterpart to :class:`FileProcessorRegistry`.

    Construct via ``FileProcessorRegistry.create_isolated()`` (empty) or
    ``FileProcessorRegistry.snapshot()`` (pre-populated copy of the global registry).
    Exposes the same method names as the classmethods above so a caller that accepts
    "a registry" can be handed either the ``FileProcessorRegistry`` class or an
    instance of this class interchangeably.
    """

    def __init__(self) -> None:
        self._processors: list[BaseFileProcessor] = []
        self._extension_cache: dict[str, BaseFileProcessor] = {}
        self._can_process_meta: dict[BaseFileProcessor, _CanProcessMeta] = {}

    def register(self, processor: BaseFileProcessor) -> None:
        """Register a file processor on this isolated instance only."""
        _register_processor(
            self._processors, self._extension_cache, self._can_process_meta, processor
        )

    def register_class(self, processor_class: type[BaseFileProcessor]) -> None:
        """Register a processor class (creates instance automatically)."""
        self.register(processor_class())

    def get_processor(
        self, extension: str, file_path: str = "", mime_type: str = ""
    ) -> BaseFileProcessor | None:
        """Get the appropriate processor for a file extension from this instance."""
        return _resolve_processor(
            self._processors,
            self._can_process_meta,
            self._extension_cache,
            extension,
            file_path,
            mime_type,
        )

    def get_all_processors(self) -> list[BaseFileProcessor]:
        """Get all processors registered on this isolated instance."""
        return self._processors.copy()

    def get_supported_extensions(self) -> list[str]:
        """Get supported file extensions for this isolated instance."""
        return _list_supported_extensions(self._processors)
