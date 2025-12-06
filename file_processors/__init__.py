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
from file_processors.msg_processor import MsgProcessor
from file_processors.ods_processor import OdsProcessor
from file_processors.pptx_processor import PptxProcessor, PptProcessor
from file_processors.yaml_processor import YamlProcessor
from file_processors.image_processor import ImageProcessor
from file_processors.zip_processor import ZipProcessor
from file_processors.sqlite_processor import SqliteProcessor
from file_processors.vcf_processor import VcfProcessor
from file_processors.mbox_processor import MboxProcessor
from file_processors.properties_processor import PropertiesProcessor
from file_processors.ical_processor import IcalProcessor
from file_processors.markdown_processor import MarkdownProcessor

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
    "MsgProcessor",
    "OdsProcessor",
    "PptxProcessor",
    "PptProcessor",
    "YamlProcessor",
    "ImageProcessor",
    "ZipProcessor",
    "SqliteProcessor",
    "VcfProcessor",
    "MboxProcessor",
    "PropertiesProcessor",
    "IcalProcessor",
    "MarkdownProcessor",
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
    MsgProcessor(),
    OdsProcessor(),
    PptxProcessor(),
    PptProcessor(),
    YamlProcessor(),
    ImageProcessor(),
    ZipProcessor(),
    SqliteProcessor(),
    VcfProcessor(),
    MboxProcessor(),
    PropertiesProcessor(),
    IcalProcessor(),
    MarkdownProcessor(),
]

# Register all processors with the registry
for processor in _registered_processors:
    FileProcessorRegistry.register(processor)
