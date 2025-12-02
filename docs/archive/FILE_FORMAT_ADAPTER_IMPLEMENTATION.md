# File Format Adapter Implementation

## Overview

This document describes the file format adapter system that allows easy integration of new file formats without modifying the main application code.

## Architecture

### Registry Pattern

The system uses a **Registry Pattern** for automatic processor discovery and registration:

- **FileProcessorRegistry**: Central registry that manages all file processors
- **Automatic Registration**: Processors are automatically registered when the `file_processors` module is imported
- **Extension-based Lookup**: Fast lookup of processors by file extension with caching

### Base Class

**BaseFileProcessor** is the abstract base class that all processors must inherit from:

```python
class BaseFileProcessor(ABC):
    @abstractmethod
    def extract_text(self, file_path: str) -> Union[str, Iterator[str]]:
        """Extract text content from a file."""
        pass
    
    @staticmethod
    def can_process(extension: str, file_path: str = "") -> bool:
        """Check if this processor can handle the given file extension."""
        return False
```

### Adding a New File Format

To add support for a new file format, simply:

1. **Create a new processor class** in `file_processors/`:
   ```python
   class MyFormatProcessor(BaseFileProcessor):
       def extract_text(self, file_path: str) -> str:
           # Implementation here
           return extracted_text
       
       @staticmethod
       def can_process(extension: str) -> bool:
           return extension.lower() == ".myformat"
   ```

2. **Import and register** in `file_processors/__init__.py`:
   ```python
   from file_processors.my_format_processor import MyFormatProcessor
   
   # Add to __all__
   __all__ = [..., "MyFormatProcessor"]
   
   # Add to _registered_processors list
   _registered_processors = [
       ...,
       MyFormatProcessor(),
   ]
   ```

3. **That's it!** The processor will be automatically available in the main application.

## Currently Supported Formats

### Implemented Formats

1. **PDF** (`.pdf`) - Using `pdfminer.six`
2. **DOCX** (`.docx`) - Using `python-docx`
3. **HTML** (`.html`, `.htm`) - Using `beautifulsoup4`
4. **Text** (`.txt`, no extension with `text/plain` MIME type) - Built-in
5. **CSV** (`.csv`) - Built-in `csv` module
6. **JSON** (`.json`) - Built-in `json` module
7. **RTF** (`.rtf`) - Using `striprtf`
8. **ODT** (`.odt`) - Using `odfpy`
9. **EML** (`.eml`) - Built-in `email` module
10. **XLSX** (`.xlsx`) - Using `openpyxl` ✨ NEW
11. **XLS** (`.xls`) - Using `xlrd` ✨ NEW
12. **XML** (`.xml`) - Built-in `xml.etree.ElementTree` ✨ NEW
13. **MSG** (`.msg`) - Using `extract-msg` ✨ NEW
14. **ODS** (`.ods`) - Using `odfpy` ✨ NEW
15. **PPTX** (`.pptx`) - Using `python-pptx` ✨ NEW
16. **YAML** (`.yaml`, `.yml`) - Using `PyYAML` ✨ NEW

### Format-Specific Features

#### PDF Processor
- Returns an **Iterator** for chunked processing (memory-efficient for large PDFs)
- Processes page by page to avoid loading entire file into memory

#### Text Processor
- Handles files with `.txt` extension
- Also handles files without extension that have `text/plain` MIME type
- Requires `file_path` parameter in `can_process()` for MIME type checking

#### XLSX/XLS Processors
- Extract all cell values from all worksheets
- Only extract actual values (not formulas)
- Handle large spreadsheets efficiently

#### XML Processor
- Recursively extracts text from all elements
- Extracts attribute values
- Handles malformed XML with fallback text extraction

#### MSG Processor
- Extracts email headers (From, To, Cc, Bcc, Subject, etc.)
- Extracts body content (plain text and HTML)
- Extracts attachment metadata (filenames)
- Extracts email addresses from various properties
- Handles HTML body content with tag removal

#### ODS Processor
- Extracts all cell values from all sheets
- Similar to Excel in terms of PII content
- Uses OpenDocument format (LibreOffice/OpenOffice)

#### PPTX Processor
- Extracts text from slides (text boxes, shapes, tables)
- Extracts text from notes pages
- Handles different shape types and tables
- Note: Older PPT format (97-2003) is not supported

#### YAML Processor
- Recursively extracts all string values (keys and values)
- Handles nested structures, arrays, and objects
- Similar to JSON processor in functionality
- Handles malformed YAML with fallback text extraction

## Usage in Main Application

The main application (`main.py`) uses the registry like this:

```python
from file_processors import FileProcessorRegistry

# Get processor for a file
processor = FileProcessorRegistry.get_processor(extension, file_path)

if processor:
    # Process the file
    text = processor.extract_text(file_path)
    # ... analyze text for PII
```

## Benefits

1. **Modularity**: Each format is self-contained in its own processor class
2. **Extensibility**: Adding new formats requires minimal code changes
3. **Maintainability**: Easy to test and debug individual processors
4. **Performance**: Extension-based caching for fast processor lookup
5. **Type Safety**: Clear interface through abstract base class

## Future Enhancements

Potential improvements for the adapter system:

1. **Plugin System**: Allow external processors to be loaded dynamically
2. **Priority System**: Allow processors to specify priority for ambiguous extensions
3. **Metadata Extraction**: Extend base class to support metadata extraction
4. **Streaming Support**: Better support for streaming processors for very large files
5. **Format Detection**: Improve format detection beyond just file extensions

## Testing

Each processor should be tested independently. See `tests/test_file_processors.py` for examples.

## Dependencies

New formats may require additional dependencies. Add them to `requirements.txt`:

- `openpyxl` - For XLSX files
- `xlrd` - For XLS files (older Excel format)
- `extract-msg` - For MSG files (Outlook email format)
- `python-pptx` - For PPTX files (PowerPoint)
- `PyYAML` - For YAML files
- `odfpy` - For ODT and ODS files (already present)
- Built-in modules: `csv`, `json`, `xml.etree.ElementTree`, `email`
