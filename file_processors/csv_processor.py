"""CSV file processor using Python's built-in csv module."""

import csv
import io

from file_processors.base_processor import BaseFileProcessor, read_text_with_fallback
from file_processors.xlsx_processor import _format_sheet_rows


class CsvProcessor(BaseFileProcessor):
    """Processor for CSV files.

    Extracts text from CSV files using Python's built-in csv module.
    Handles different delimiters (comma, semicolon, tab) and encodings.
    Extracts all cell values as text for PII detection.
    """

    def extract_text(self, file_path: str) -> str:
        """Extract text from a CSV file.

        Attempts to detect the delimiter automatically by trying common delimiters.
        The first row is treated as a header when present, so each value is emitted
        as ``"<column>: <value>"`` and downstream detection keeps the column context
        (e.g. a value under an "IBAN" column).  One line per record preserves row
        boundaries so entities from different records do not fuse.

        Args:
            file_path: Path to the CSV file

        Returns:
            Extracted text content from all cells as a string

        Raises:
            UnicodeDecodeError: If file encoding cannot be decoded
            PermissionError: If file cannot be accessed
            FileNotFoundError: If file does not exist
            Exception: For other CSV processing errors
        """
        content = read_text_with_fallback(file_path)

        # Detect delimiter from first 1024 chars
        sample = content[:1024]
        delimiters = [",", ";", "\t", "|"]
        delimiter_counts = {d: sample.count(d) for d in delimiters}
        detected_delimiter = ","
        if max(delimiter_counts.values()) > 0:
            detected_delimiter = max(delimiter_counts, key=delimiter_counts.get)

        reader = csv.reader(io.StringIO(content), delimiter=detected_delimiter)
        return "\n".join(_format_sheet_rows(reader))

    @staticmethod
    def can_process(extension: str) -> bool:
        """Check if this processor can handle CSV files."""
        return extension.lower() == ".csv"
