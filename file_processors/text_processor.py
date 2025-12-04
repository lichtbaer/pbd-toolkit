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
    def can_process(extension: str, file_path: str = "", mime_type: str = "") -> bool:
        """Check if this processor can handle the file.
        
        Args:
            extension: File extension (may be empty for text files)
            file_path: Full path to the file (for mime type checking)
            mime_type: Detected MIME type (from magic number detection)
            
        Returns:
            True if file is a plain text file, False otherwise
        """
        # Check by extension
        if extension.lower() == ".txt":
            return True
        
        # Check by detected MIME type (from magic numbers)
        if mime_type:
            return mime_type == "text/plain"
        
        # Fallback: check by file_path MIME type guessing
        if extension == "" and file_path:
            guessed_mime, _ = mimetypes.guess_type(file_path)
            return guessed_mime == "text/plain"
        
        return False
