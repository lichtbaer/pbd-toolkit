"""ODS file processor using odfpy library."""

from file_processors.base_processor import BaseFileProcessor
from odf.opendocument import load
from odf.table import Table, TableRow, TableCell


class OdsProcessor(BaseFileProcessor):
    """Processor for ODS (OpenDocument Spreadsheet) files.

    Extracts text from ODS files using the odfpy library.
    Extracts all cell values from all sheets for PII detection.
    Similar structure to XLSX but uses OpenDocument format.
    """

    def extract_text(self, file_path: str) -> str:
        """Extract text from an ODS file.

        Extracts all cell values from all worksheets in the workbook.

        Args:
            file_path: Path to the ODS file

        Returns:
            Extracted text content from all cells as a string

        Raises:
            PermissionError: If file cannot be accessed
            FileNotFoundError: If file does not exist
            Exception: For other ODS processing errors
        """
        text_parts: list[str] = []

        try:
            doc = load(file_path)

            # Extract text from all tables (sheets in ODS)
            for table in doc.getElementsByType(Table):
                for row in table.getElementsByType(TableRow):
                    for cell in row.getElementsByType(TableCell):
                        cell_text = self._extract_text_from_element(cell)
                        if cell_text and cell_text.strip():
                            text_parts.append(cell_text.strip())

        except Exception as e:
            # Re-raise with context
            raise Exception(f"Error processing ODS file: {str(e)}") from e

        return " ".join(text_parts)

    def _extract_text_from_element(self, element) -> str:
        """Recursively extract text from an ODS element.

        Args:
            element: ODS element to extract text from

        Returns:
            Extracted text content
        """
        text_parts: list[str] = []

        # Get direct text content (for TextNode elements)
        if hasattr(element, "data") and element.data:
            text_parts.append(str(element.data))

        # Recursively process child nodes
        if hasattr(element, "childNodes"):
            for child in element.childNodes:
                # Text nodes have data attribute
                if hasattr(child, "data") and child.data:
                    text_parts.append(str(child.data))
                # Element nodes have childNodes
                elif hasattr(child, "childNodes"):
                    child_text = self._extract_text_from_element(child)
                    if child_text:
                        text_parts.append(child_text)

        return " ".join(text_parts)

    @staticmethod
    def can_process(extension: str) -> bool:
        """Check if this processor can handle ODS files."""
        return extension.lower() == ".ods"
