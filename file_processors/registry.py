"""File processor registry for automatic registration and discovery of processors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Type

from file_processors.base_processor import BaseFileProcessor


@dataclass(frozen=True)
class _CanProcessMeta:
    """Cached metadata about a processor's `can_process` signature.

    Avoids calling `inspect.signature` in the per-file hot path.
    """

    positional_param_count: int


class FileProcessorRegistry:
    """Registry for file processors with automatic registration.

    This registry allows processors to be automatically discovered and registered,
    making it easy to add new file format support without modifying main.py.
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
    def register_class(cls, processor_class: Type[BaseFileProcessor]) -> None:
        """Register a processor class (creates instance automatically).

        Args:
            processor_class: Processor class to register
        """
        processor = processor_class()
        cls.register(processor)

    @staticmethod
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
                p.kind
                in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
                for p in sig.parameters.values()
            ):
                count = 3
            count = max(1, min(3, count))
            return _CanProcessMeta(positional_param_count=count)
        except Exception:
            # Conservative: assume the most flexible signature.
            return _CanProcessMeta(positional_param_count=3)

    @classmethod
    def get_processor(
        cls, extension: str, file_path: str = "", mime_type: str = ""
    ) -> Optional[BaseFileProcessor]:
        """Get the appropriate processor for a file extension.

        Args:
            extension: File extension (e.g., '.pdf', '.docx')
            file_path: Full path to the file (optional, needed for some processors)
            mime_type: Detected MIME type (optional, for magic number detection)

        Returns:
            Appropriate processor instance or None if no processor available
        """
        # Check cache first (only for processors that don't need file_path or mime_type)
        if extension and extension in cls._extension_cache and not mime_type:
            return cls._extension_cache[extension]

        # Check each processor
        for processor in cls._processors:
            meta = cls._can_process_meta.get(processor)
            if meta is None:
                meta = cls._compute_can_process_meta(processor)
                cls._can_process_meta[processor] = meta

            try:
                if meta.positional_param_count >= 3:
                    if processor.can_process(extension, file_path, mime_type):
                        # Safe to cache only when MIME type is not involved.
                        if extension and not mime_type:
                            cls._extension_cache[extension] = processor
                        return processor
                elif meta.positional_param_count == 2:
                    if processor.can_process(extension, file_path):
                        # Don't cache: may depend on file_path.
                        return processor
                else:
                    if processor.can_process(extension):
                        if extension and not mime_type:
                            cls._extension_cache[extension] = processor
                        return processor
            except (TypeError, ValueError):
                continue

        return None

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
