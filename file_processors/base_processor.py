"""Base class for file processors."""

from abc import ABC, abstractmethod
from typing import Any, Iterator, Union


class BaseFileProcessor(ABC):
    """Abstract base class for file processors.
    
    All file processors should inherit from this class and implement
    the extract_text method.
    
    Processors can optionally implement can_process to indicate which
    file extensions they support. The default implementation returns False.
    """
    
    @abstractmethod
    def extract_text(self, file_path: str) -> Union[str, Iterator[str]]:
        """Extract text content from a file.
        
        Args:
            file_path: Path to the file to process
            
        Returns:
            Extracted text content as a string or iterator of strings
            (for chunked processing of large files)
            
        Raises:
            Various exceptions depending on the file type and processing issues
        """
        pass
    
    @staticmethod
    def can_process(extension: str, file_path: str = "") -> bool:
        """Check if this processor can handle the given file extension.
        
        Args:
            extension: File extension (e.g., '.pdf', '.docx')
            file_path: Optional full path to the file (for processors that need
                      to check file content or MIME type)
            
        Returns:
            True if this processor can handle the extension, False otherwise
            
        Note:
            Most processors only need the extension parameter. Some processors
            (like TextProcessor) may need the file_path to check MIME types.
        """
        return False
