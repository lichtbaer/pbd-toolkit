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

Isolation for tests and API/server use
---------------------------------------
``_processors``/``_extension_cache``/``_can_process_meta`` are shared, process-wide
state populated once at import time (see ``file_processors/__init__.py``). Calling
``register()`` or ``clear()`` directly in a test mutates that shared state for
every test that runs afterwards in the same process unless the caller manually
saves and restores it. Use ``FileProcessorRegistry.isolated()`` to scope such
mutations to a ``with`` block instead; the previous processor list, cache, and
signature-metadata table are restored on exit even if the block raises.

Use ``FileProcessorRegistry.snapshot()`` to obtain an independent, read-only view
of the processors registered at a point in time — useful for a long-lived
API/server process that wants a stable processor set for a request, decoupled
from whatever the global registry looks like by the time the request is served.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
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


def _find_processor(
    processors: list[BaseFileProcessor],
    can_process_meta: dict[BaseFileProcessor, _CanProcessMeta],
    extension_cache: dict[str, BaseFileProcessor],
    extension: str,
    file_path: str,
    mime_type: str,
) -> BaseFileProcessor | None:
    """Find the processor claiming *extension* among *processors*.

    Shared by ``FileProcessorRegistry.get_processor`` and
    ``FileProcessorRegistrySnapshot.get_processor`` so both use identical
    dispatch/caching logic, differing only in which processor list, metadata
    table, and cache they read and write. *extension_cache* and
    *can_process_meta* are mutated in place (cache-fill), which is safe because
    each caller passes its own independent dict.
    """
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


class FileProcessorRegistrySnapshot:
    """Independent, read-only view of the processors registered at snapshot time.

    Unlike ``FileProcessorRegistry``, later calls to ``FileProcessorRegistry.register()``
    do not affect an already-taken snapshot. Obtain one via
    ``FileProcessorRegistry.snapshot()``. Keeps its own extension cache, so lookups
    against the snapshot never populate (or read) the global registry's cache.
    """

    def __init__(
        self,
        processors: list[BaseFileProcessor],
        can_process_meta: dict[BaseFileProcessor, _CanProcessMeta],
    ):
        self._processors = list(processors)
        self._can_process_meta = dict(can_process_meta)
        self._extension_cache: dict[str, BaseFileProcessor] = {}

    def get_processor(
        self, extension: str, file_path: str = "", mime_type: str = ""
    ) -> BaseFileProcessor | None:
        """Get the appropriate processor for a file extension from this snapshot."""
        return _find_processor(
            self._processors,
            self._can_process_meta,
            self._extension_cache,
            extension,
            file_path,
            mime_type,
        )

    def get_all_processors(self) -> list[BaseFileProcessor]:
        """Get all processors captured in this snapshot."""
        return list(self._processors)


class FileProcessorRegistry:
    """Registry for file processors with automatic registration.

    Class-level state (``_processors``, ``_extension_cache``) is shared across all
    call sites without instantiation.  This is intentional: there is exactly one
    global processor list per Python process, matching the single-registry pattern.

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
        if processor not in cls._processors:
            cls._processors.append(processor)
            # Clear cache when new processor is registered
            cls._extension_cache.clear()
            cls._can_process_meta[processor] = cls._compute_can_process_meta(processor)

    @classmethod
    def register_class(cls, processor_class: type[BaseFileProcessor]) -> None:
        """Register a processor class (creates instance automatically).

        Args:
            processor_class: Processor class to register
        """
        processor = processor_class()
        cls.register(processor)

    @staticmethod
    def _compute_can_process_meta(processor: BaseFileProcessor) -> _CanProcessMeta:
        """Compute `can_process` signature metadata once per processor."""
        return _compute_can_process_meta(processor)

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
        return _find_processor(
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
    def snapshot(cls) -> FileProcessorRegistrySnapshot:
        """Return an independent, read-only snapshot of the current registry.

        Returns:
            A ``FileProcessorRegistrySnapshot`` unaffected by later ``register()``
            or ``clear()`` calls against the global registry.
        """
        return FileProcessorRegistrySnapshot(cls._processors, cls._can_process_meta)

    @classmethod
    @contextmanager
    def isolated(cls) -> Iterator[type[FileProcessorRegistry]]:
        """Scope registry mutations to this ``with`` block.

        Saves the current processor list, extension cache, and signature-metadata
        table; lets the block ``register()``/``clear()`` freely via the normal
        ``FileProcessorRegistry`` API; and restores all three on exit — including
        when the block raises. Intended for tests that need a fake processor or a
        cleared registry without leaking that state into tests that run afterwards
        in the same process.

        Yields:
            The ``FileProcessorRegistry`` class itself, so callers can keep using
            the familiar ``FileProcessorRegistry.register(...)`` API inside the
            block.
        """
        previous_processors = cls._processors
        previous_cache = cls._extension_cache
        previous_meta = cls._can_process_meta
        previous_initialized = cls._initialized
        cls._processors = list(previous_processors)
        cls._extension_cache = dict(previous_cache)
        cls._can_process_meta = dict(previous_meta)
        try:
            yield cls
        finally:
            cls._processors = previous_processors
            cls._extension_cache = previous_cache
            cls._can_process_meta = previous_meta
            cls._initialized = previous_initialized

    @classmethod
    def get_supported_extensions(cls) -> list[str]:
        """Get list of all supported file extensions.

        Returns:
            List of supported extensions (e.g., ['.pdf', '.docx', ...])
        """
        extensions = []
        for processor in cls._processors:
            # Try to determine supported extensions from processor
            # This is a heuristic - processors should ideally expose this
            if hasattr(processor, "can_process"):
                # Test common extensions
                common_extensions = [
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
                for ext in common_extensions:
                    if processor.can_process(ext):
                        if ext not in extensions:
                            extensions.append(ext)
        return sorted(extensions)
