"""PDF file processor using pdfminer.six, with an optional OCR fallback."""

import logging
from collections.abc import Iterator

from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer

from core import constants
from file_processors.base_processor import BaseFileProcessor

_logger = logging.getLogger(__name__)


def _ocr_available() -> bool:
    """Return True when the optional OCR stack (pdf2image + pytesseract) is importable.

    OCR is opt-in via the ``[ocr]`` extra: when the libraries are installed it is used
    automatically as a fallback for pages with no embedded text (i.e. scanned PDFs).
    When they are absent this is a no-op, so the default install is unaffected.
    """
    try:
        import pdf2image  # noqa: F401
        import pytesseract  # noqa: F401
    except Exception:
        return False
    return True


def _ocr_page(file_path: str, page_number: int) -> str:
    """OCR a single (1-based) PDF page; returns "" on any failure or if OCR is absent."""
    try:
        from pdf2image import convert_from_path
        from pytesseract import image_to_string

        images = convert_from_path(
            file_path, first_page=page_number, last_page=page_number
        )
        return "\n".join(image_to_string(img) for img in images)
    except Exception as exc:  # pragma: no cover - depends on optional native libs
        _logger.debug("OCR failed for %s page %d: %s", file_path, page_number, exc)
        return ""


class PdfProcessor(BaseFileProcessor):
    """Processor for PDF files.

    Extracts text from PDF files using pdfminer.six, accumulating all text containers
    of a page before yielding so that short standalone values (e.g. an IBAN on its own
    line) are not dropped — the previous per-container minimum-length filter discarded
    them.  When a page has no embedded text and the optional OCR stack is installed, the
    page is OCR'd as a fallback so scanned PDFs are no longer silently empty.
    """

    def extract_text(self, file_path: str) -> Iterator[str]:
        """Extract text from a PDF file page by page.

        Args:
            file_path: Path to the PDF file

        Yields:
            Text for each page (accumulated across the page's text containers)

        Raises:
            PermissionError: If file cannot be accessed
            FileNotFoundError: If file does not exist
            Exception: For other PDF processing errors
        """
        ocr_enabled = _ocr_available()
        for page_number, page_layout in enumerate(extract_pages(file_path), start=1):
            page_parts = [
                element.get_text()
                for element in page_layout
                if isinstance(element, LTTextContainer)
            ]
            page_text = self._finalize_page(
                "".join(page_parts),
                (lambda: _ocr_page(file_path, page_number)) if ocr_enabled else None,
            )
            if page_text:
                yield page_text

    @staticmethod
    def _finalize_page(page_text: str, ocr_callable) -> str:
        """Decide what to yield for a page given its extracted text and an OCR fallback.

        Returns the page text when it has meaningful content (length ≥
        ``MIN_PDF_TEXT_LENGTH``).  Otherwise, if an OCR callable is provided (the OCR
        stack is installed), the OCR result is returned.  Pure function for testability.
        """
        if len(page_text.strip()) >= constants.MIN_PDF_TEXT_LENGTH:
            return page_text
        if ocr_callable is not None:
            ocr_text = ocr_callable()
            if ocr_text and ocr_text.strip():
                return ocr_text
        return ""

    @staticmethod
    def can_process(extension: str) -> bool:
        """Check if this processor can handle PDF files."""
        return extension.lower() == ".pdf"
