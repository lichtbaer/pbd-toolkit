"""DOCX file processor using python-docx."""

import docx
import docx.opc.exceptions
from file_processors.base_processor import BaseFileProcessor


class DocxProcessor(BaseFileProcessor):
    """Processor for DOCX files.
    
    Extracts text from DOCX files using python-docx. Currently only extracts
    text from paragraphs, not from headers, footers, or tables.
    """
    
    def extract_text(self, file_path: str) -> str:
        """Extract text from a DOCX file.
        
        Args:
            file_path: Path to the DOCX file
            
        Returns:
            Extracted text content as a string
            
        Raises:
            docx.opc.exceptions.PackageNotFoundError: If DOCX is empty or protected
            PermissionError: If file cannot be accessed
            FileNotFoundError: If file does not exist
            Exception: For other DOCX processing errors
        """
        doc: docx.Document = docx.Document(file_path)
        text: str = ""
        
        for paragraph in doc.paragraphs:
            text += paragraph.text
        
        return text
    
    @staticmethod
    def can_process(extension: str) -> bool:
        """Check if this processor can handle DOCX files."""
        return extension.lower() == ".docx"
