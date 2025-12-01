"""ODT file processor using odfpy library."""

from file_processors.base_processor import BaseFileProcessor
from odf.opendocument import load
from odf.text import P, H, Span
from odf.table import Table, TableRow, TableCell


class OdtProcessor(BaseFileProcessor):
    """Processor for ODT (OpenDocument Text) files.
    
    Extracts text from ODT files using the odfpy library.
    Extracts text from paragraphs, headings, and tables.
    Similar structure to DOCX but uses OpenDocument format.
    """
    
    def extract_text(self, file_path: str) -> str:
        """Extract text from an ODT file.
        
        Args:
            file_path: Path to the ODT file
            
        Returns:
            Extracted text content from paragraphs, headings, and tables
            
        Raises:
            PermissionError: If file cannot be accessed
            FileNotFoundError: If file does not exist
            Exception: For other ODT processing errors
        """
        text_parts: list[str] = []
        
        try:
            doc = load(file_path)
            
            # Extract text from paragraphs and headings
            for paragraph in doc.getElementsByType(P):
                text = self._extract_text_from_element(paragraph)
                if text and text.strip():
                    text_parts.append(text.strip())
            
            # Extract text from headings
            for heading in doc.getElementsByType(H):
                text = self._extract_text_from_element(heading)
                if text and text.strip():
                    text_parts.append(text.strip())
            
            # Extract text from tables
            for table in doc.getElementsByType(Table):
                for row in table.getElementsByType(TableRow):
                    for cell in row.getElementsByType(TableCell):
                        cell_text = self._extract_text_from_element(cell)
                        if cell_text and cell_text.strip():
                            text_parts.append(cell_text.strip())
            
        except Exception as e:
            # Re-raise with context
            raise Exception(f"Error processing ODT file: {str(e)}") from e
        
        return ' '.join(text_parts)
    
    def _extract_text_from_element(self, element) -> str:
        """Recursively extract text from an ODT element.
        
        Args:
            element: ODT element to extract text from
            
        Returns:
            Extracted text content
        """
        text_parts: list[str] = []
        
        # Get direct text content (for TextNode elements)
        if hasattr(element, 'data') and element.data:
            text_parts.append(str(element.data))
        
        # Recursively process child nodes
        if hasattr(element, 'childNodes'):
            for child in element.childNodes:
                # Text nodes have data attribute
                if hasattr(child, 'data') and child.data:
                    text_parts.append(str(child.data))
                # Element nodes have childNodes
                elif hasattr(child, 'childNodes'):
                    child_text = self._extract_text_from_element(child)
                    if child_text:
                        text_parts.append(child_text)
        
        return ' '.join(text_parts)
    
    @staticmethod
    def can_process(extension: str) -> bool:
        """Check if this processor can handle ODT files."""
        return extension.lower() == ".odt"
