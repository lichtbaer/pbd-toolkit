"""File processor registry for automatic registration and discovery of processors."""

from typing import Optional, Type
from file_processors.base_processor import BaseFileProcessor


class FileProcessorRegistry:
    """Registry for file processors with automatic registration.
    
    This registry allows processors to be automatically discovered and registered,
    making it easy to add new file format support without modifying main.py.
    """
    
    _processors: list[BaseFileProcessor] = []
    _extension_cache: dict[str, BaseFileProcessor] = {}
    _initialized: bool = False
    
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
    
    @classmethod
    def register_class(cls, processor_class: Type[BaseFileProcessor]) -> None:
        """Register a processor class (creates instance automatically).
        
        Args:
            processor_class: Processor class to register
        """
        processor = processor_class()
        cls.register(processor)
    
    @classmethod
    def get_processor(cls, extension: str, file_path: str = "") -> Optional[BaseFileProcessor]:
        """Get the appropriate processor for a file extension.
        
        Args:
            extension: File extension (e.g., '.pdf', '.docx')
            file_path: Full path to the file (optional, needed for some processors)
            
        Returns:
            Appropriate processor instance or None if no processor available
        """
        # Check cache first (only for processors that don't need file_path)
        if extension and extension in cls._extension_cache:
            return cls._extension_cache[extension]
        
        # Check each processor
        for processor in cls._processors:
            if hasattr(processor, 'can_process'):
                # Check if can_process accepts file_path parameter
                import inspect
                try:
                    sig = inspect.signature(processor.can_process)
                    params = list(sig.parameters.keys())
                    
                    # Check if processor needs file_path (has file_path parameter)
                    needs_file_path = len(params) >= 2 and 'file_path' in params
                    
                    if needs_file_path:
                        # Processor needs file_path (e.g., TextProcessor)
                        if processor.can_process(extension, file_path):
                            # Don't cache processors that need file_path by extension alone
                            return processor
                    else:
                        # Standard can_process with just extension
                        if processor.can_process(extension):
                            # Cache by extension for processors that don't need file_path
                            cls._extension_cache[extension] = processor
                            return processor
                except (TypeError, ValueError):
                    # Fallback: try with just extension if signature inspection fails
                    try:
                        if processor.can_process(extension):
                            cls._extension_cache[extension] = processor
                            return processor
                    except TypeError:
                        # If that also fails, try with file_path
                        try:
                            if processor.can_process(extension, file_path):
                                return processor
                        except (TypeError, ValueError):
                            # Skip this processor if can_process doesn't work
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
            if hasattr(processor, 'can_process'):
                # Test common extensions
                common_extensions = [
                    '.pdf', '.docx', '.html', '.htm', '.txt', '.csv', '.json',
                    '.rtf', '.odt', '.xlsx', '.xls', '.xml', '.pptx', '.ppt',
                    '.eml', '.msg', '.ods', '.yaml', '.yml', '.md'
                ]
                for ext in common_extensions:
                    if processor.can_process(ext):
                        if ext not in extensions:
                            extensions.append(ext)
        return sorted(extensions)
