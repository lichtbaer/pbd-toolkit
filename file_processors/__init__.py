"""File processors for extracting text from different file formats."""

from file_processors.base_processor import BaseFileProcessor
from file_processors.pdf_processor import PdfProcessor
from file_processors.docx_processor import DocxProcessor
from file_processors.html_processor import HtmlProcessor
from file_processors.text_processor import TextProcessor
from file_processors.csv_processor import CsvProcessor
from file_processors.json_processor import JsonProcessor
from file_processors.rtf_processor import RtfProcessor
from file_processors.odt_processor import OdtProcessor
from file_processors.eml_processor import EmlProcessor

__all__ = [
    "BaseFileProcessor",
    "PdfProcessor",
    "DocxProcessor",
    "HtmlProcessor",
    "TextProcessor",
    "CsvProcessor",
    "JsonProcessor",
    "RtfProcessor",
    "OdtProcessor",
    "EmlProcessor",
]
