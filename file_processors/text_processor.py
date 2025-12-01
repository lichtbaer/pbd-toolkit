"""Plain text file processor."""

import mimetypes
from file_processors.base_processor import BaseFileProcessor


class TextProcessor(BaseFileProcessor):
    """Processor for plain text files.
    
    Handles files with .txt extension or files without extension
    that have mime type "text/plain".
    """
    
    def extract_text(self, file_path: str) -> str:
        """Extract text from a plain text file.
        
        Args:
            file_path: Path to the text file
            
        Returns:
            File content as a string
            
        Raises:
            UnicodeDecodeError: If file encoding cannot be decoded
            PermissionError: If file cannot be accessed
            FileNotFoundError: If file does not exist
            Exception: For other file reading errors
        """
        with open(file_path, encoding="utf-8", errors="replace") as doc:
            return doc.read()
    
    @staticmethod
    def can_process(extension: str, file_path: str) -> bool:
        """Check if this processor can handle the file.
        
        Args:
            extension: File extension (may be empty for text files)
            file_path: Full path to the file (for mime type checking)
            
        Returns:
            True if file is a plain text file, False otherwise
        """
        if extension.lower() == ".txt":
            return True
        if extension == "":
            mime_type, _ = mimetypes.guess_type(file_path)
            return mime_type == "text/plain"
        return False
