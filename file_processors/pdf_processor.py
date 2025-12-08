"""PDF file processor using pdfminer.six."""

from typing import Iterator
from file_processors.base_processor import BaseFileProcessor
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer
import constants


class PdfProcessor(BaseFileProcessor):
    """Processor for PDF files.

    Extracts text from PDF files using pdfminer.six. Only works for PDFs
    with actual text embeddings. Scanned PDFs without OCR are not supported.
    """

    def extract_text(self, file_path: str) -> Iterator[str]:
        """Extract text from a PDF file page by page.

        Args:
            file_path: Path to the PDF file

        Yields:
            Text chunks from each page (to avoid loading entire file into memory)

        Raises:
            PermissionError: If file cannot be accessed
            FileNotFoundError: If file does not exist
            Exception: For other PDF processing errors
        """
        for page_layout in extract_pages(file_path):
            for text_container in page_layout:
                if isinstance(text_container, LTTextContainer):
                    text: str = text_container.get_text()

                    # Workaround for PDFs with messed-up text embeddings that only
                    # consist of very short character sequences
                    if len(text) >= constants.MIN_PDF_TEXT_LENGTH:
                        yield text

    @staticmethod
    def can_process(extension: str) -> bool:
        """Check if this processor can handle PDF files."""
        return extension.lower() == ".pdf"
