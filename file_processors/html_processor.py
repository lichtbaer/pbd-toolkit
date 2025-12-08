"""HTML file processor using BeautifulSoup4."""

from bs4 import BeautifulSoup
from file_processors.base_processor import BaseFileProcessor


class HtmlProcessor(BaseFileProcessor):
    """Processor for HTML files.

    Extracts text from HTML files using BeautifulSoup4, removing all markup.
    """

    def extract_text(self, file_path: str) -> str:
        """Extract text from an HTML file.

        Args:
            file_path: Path to the HTML file

        Returns:
            Extracted text content without HTML markup

        Raises:
            UnicodeDecodeError: If file encoding cannot be decoded
            PermissionError: If file cannot be accessed
            FileNotFoundError: If file does not exist
            Exception: For other HTML processing errors
        """
        with open(file_path, encoding="utf-8", errors="replace") as doc:
            soup: BeautifulSoup = BeautifulSoup(doc, "html.parser")
            return soup.get_text()

    @staticmethod
    def can_process(extension: str) -> bool:
        """Check if this processor can handle HTML files."""
        return extension.lower() in [".html", ".htm"]
