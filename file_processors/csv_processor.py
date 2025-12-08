"""CSV file processor using Python's built-in csv module."""

import csv
from typing import Optional
from file_processors.base_processor import BaseFileProcessor


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
        last_error: Optional[UnicodeDecodeError] = None

        # Try different encodings
        encodings = ["utf-8", "utf-8-sig", "latin-1", "cp1252", "iso-8859-1"]

        for encoding in encodings:
            try:
                with open(file_path, "r", encoding=encoding, newline="") as csvfile:
                    # Try to detect delimiter by reading first line
                    sample = csvfile.read(1024)
                    csvfile.seek(0)

                    # Try common delimiters
                    delimiters = [",", ";", "\t", "|"]
                    detected_delimiter = ","

                    # Simple heuristic: use delimiter that appears most in first line
                    delimiter_counts = {
                        delim: sample.count(delim) for delim in delimiters
                    }
                    if max(delimiter_counts.values()) > 0:
                        detected_delimiter = max(
                            delimiter_counts, key=delimiter_counts.get
                        )

                    # Read CSV with detected delimiter
                    reader = csv.reader(csvfile, delimiter=detected_delimiter)

                    for row in reader:
                        # Extract all cell values
                        for cell in row:
                            if cell and cell.strip():  # Only add non-empty cells
                                text_parts.append(cell.strip())

                    # Successfully read with this encoding
                    return " ".join(text_parts)

            except UnicodeDecodeError as e:
                # Try next encoding
                last_error = e
                continue
            except Exception:
                # Re-raise other exceptions immediately
                raise

        # If we get here, all encodings failed
        if last_error:
            raise UnicodeDecodeError(
                last_error.encoding,
                last_error.object,
                last_error.start,
                last_error.end,
                f"Could not decode CSV file with any of the attempted encodings: {', '.join(encodings)}",
            ) from last_error

        return " ".join(text_parts)

    @staticmethod
    def can_process(extension: str) -> bool:
        """Check if this processor can handle CSV files."""
        return extension.lower() == ".csv"
