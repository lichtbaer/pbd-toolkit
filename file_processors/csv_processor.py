"""CSV file processor using Python's built-in csv module."""

import csv
import io

from file_processors.base_processor import BaseFileProcessor, read_text_with_fallback


class CsvProcessor(BaseFileProcessor):
    """Processor for CSV files.

    Extracts text from CSV files using Python's built-in csv module.
    Handles different delimiters (comma, semicolon, tab) and encodings.
    Extracts all cell values as text for PII detection.
    """

    def extract_text(self, file_path: str) -> str:
        """Extract text from a CSV file.

        Attempts to detect the delimiter automatically by trying common delimiters.
        Extracts all cell values and combines them into a single text string.

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
        text_parts: list[str] = []

        content = read_text_with_fallback(file_path)

        # Detect delimiter from first 1024 chars
        sample = content[:1024]
        delimiters = [",", ";", "\t", "|"]
        delimiter_counts = {d: sample.count(d) for d in delimiters}
        detected_delimiter = ","
        if max(delimiter_counts.values()) > 0:
            detected_delimiter = max(delimiter_counts, key=delimiter_counts.get)

        reader = csv.reader(io.StringIO(content), delimiter=detected_delimiter)
        for row in reader:
            for cell in row:
                if cell and cell.strip():
                    text_parts.append(cell.strip())

        return " ".join(text_parts)

    @staticmethod
    def can_process(extension: str) -> bool:
        """Check if this processor can handle CSV files."""
        return extension.lower() == ".csv"
