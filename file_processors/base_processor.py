"""Base class for file processors."""

from abc import ABC, abstractmethod
from typing import Any, Iterator, Union


class BaseFileProcessor(ABC):
    """Abstract base class for file processors.
    
    All file processors should inherit from this class and implement
    the extract_text method.
    """
    
    @abstractmethod
    def extract_text(self, file_path: str) -> Union[str, Iterator[str]]:
        """Extract text content from a file.
        
        Args:
            file_path: Path to the file to process
            
        Returns:
            Extracted text content as a string
            
        Raises:
            Various exceptions depending on the file type and processing issues
        """
        pass
    
    @staticmethod
    def can_process(extension: str) -> bool:
        """Check if this processor can handle the given file extension.
        
        Args:
            extension: File extension (e.g., '.pdf', '.docx')
            
        Returns:
            True if this processor can handle the extension, False otherwise
        """
        return False
