"""File processors for extracting text from different file formats."""

from file_processors.base_processor import BaseFileProcessor
from file_processors.registry import FileProcessorRegistry
from file_processors.pdf_processor import PdfProcessor
from file_processors.docx_processor import DocxProcessor
from file_processors.html_processor import HtmlProcessor
from file_processors.text_processor import TextProcessor
from file_processors.csv_processor import CsvProcessor
from file_processors.json_processor import JsonProcessor
from file_processors.rtf_processor import RtfProcessor
from file_processors.odt_processor import OdtProcessor
from file_processors.eml_processor import EmlProcessor
from file_processors.xlsx_processor import XlsxProcessor, XlsProcessor
from file_processors.xml_processor import XmlProcessor

__all__ = [
    "BaseFileProcessor",
    "FileProcessorRegistry",
    "PdfProcessor",
    "DocxProcessor",
    "HtmlProcessor",
    "TextProcessor",
    "CsvProcessor",
    "JsonProcessor",
    "RtfProcessor",
    "OdtProcessor",
    "EmlProcessor",
    "XlsxProcessor",
    "XlsProcessor",
    "XmlProcessor",
]

# Auto-register all processors
# This allows new processors to be automatically discovered
# Simply import them above and they will be registered here
_registered_processors = [
    PdfProcessor(),
    DocxProcessor(),
    HtmlProcessor(),
    TextProcessor(),
    CsvProcessor(),
    JsonProcessor(),
    RtfProcessor(),
    OdtProcessor(),
    EmlProcessor(),
    XlsxProcessor(),
    XlsProcessor(),
    XmlProcessor(),
]

# Register all processors with the registry
for processor in _registered_processors:
    FileProcessorRegistry.register(processor)
