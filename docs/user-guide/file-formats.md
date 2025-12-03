# Supported File Formats

The PII Toolkit supports a wide range of file formats for PII detection. Files are identified by their extension and processed using specialized processors.

## Document Formats

### PDF (`.pdf`)

Portable Document Format files.

**Processor**: `PdfProcessor`
- Extracts text from PDF files
- Handles PDFs with embedded text
- Processes large PDFs in chunks for memory efficiency
- Skips PDFs with very short text (likely image-only)

**Limitations**:
- Does not support OCR (image-based PDFs are skipped)
- Password-protected PDFs are reported as errors

### DOCX (`.docx`)

Microsoft Word documents (Office Open XML format).

**Processor**: `DocxProcessor`
- Extracts text from document body
- Preserves paragraph structure
- Handles Unicode characters

**Limitations**:
- Headers, footers, and table text may not be fully extracted
- Password-protected documents are reported as errors

### ODT (`.odt`)

OpenDocument Text format (used by LibreOffice, OpenOffice).

**Processor**: `OdtProcessor`
- Extracts text from ODT documents
- Handles standard ODT structure

### RTF (`.rtf`)

Rich Text Format documents.

**Processor**: `RtfProcessor`
- Extracts plain text from RTF files
- Strips RTF formatting codes

## Spreadsheet Formats

### XLSX (`.xlsx`)

Microsoft Excel spreadsheets (Office Open XML format).

**Processor**: `XlsxProcessor`
- Extracts text from all cells
- Processes all worksheets
- Handles formulas (extracts displayed values)

### XLS (`.xls`)

Microsoft Excel spreadsheets (Excel 97-2003 format).

**Processor**: `XlsProcessor`
- Extracts text from all cells
- Processes all worksheets
- Handles older Excel file format

### ODS (`.ods`)

OpenDocument Spreadsheet format.

**Processor**: `OdsProcessor`
- Extracts text from all cells
- Processes all sheets

### CSV (`.csv`)

Comma-separated values files.

**Processor**: `CsvProcessor`
- Reads CSV files
- Extracts all cell values
- Handles various delimiters and encodings

## Presentation Formats

### PPTX (`.pptx`)

Microsoft PowerPoint presentations (PowerPoint 2007+ format).

**Processor**: `PptxProcessor`
- Extracts text from slides
- Processes all slides in presentation
- Extracts text from text boxes and shapes
- Extracts text from notes pages

### PPT (`.ppt`)

Microsoft PowerPoint presentations (PowerPoint 97-2003 format).

**Processor**: `PptProcessor`
- Extracts text from older PowerPoint files
- Note: Support for older PPT format is limited

## Web Formats

### HTML (`.html`, `.htm`)

HyperText Markup Language files.

**Processor**: `HtmlProcessor`
- Extracts text content from HTML
- Removes HTML tags and scripts
- Handles various HTML encodings

### XML (`.xml`)

eXtensible Markup Language files.

**Processor**: `XmlProcessor`
- Extracts text content from XML
- Preserves text structure
- Handles various XML encodings

## Email Formats

### EML (`.eml`)

Email message files (RFC 822 format).

**Processor**: `EmlProcessor`
- Extracts text from email body
- Handles plain text and HTML emails
- Extracts email headers (subject, from, to, etc.)

### MSG (`.msg`)

Microsoft Outlook message files.

**Processor**: `MsgProcessor`
- Extracts email content
- Handles Outlook-specific format
- Extracts attachments metadata

## Data Formats

### JSON (`.json`)

JavaScript Object Notation files.

**Processor**: `JsonProcessor`
- Extracts string values from JSON
- Handles nested structures
- Preserves text content

### YAML (`.yaml`, `.yml`)

YAML Ain't Markup Language files.

**Processor**: `YamlProcessor`
- Extracts string values from YAML
- Handles nested structures
- Preserves text content

## Plain Text

### TXT (`.txt` or no extension)

Plain text files.

**Processor**: `TextProcessor`
- Reads plain text files
- Handles various encodings (UTF-8, Latin-1, etc.)
- Also processes files without extension if MIME type is `text/plain`

## File Processing

### How Files Are Identified

Files are identified by their extension (case-insensitive). The registry automatically selects the appropriate processor.

### Processing Order

1. File extension is extracted
2. Registry finds matching processor
3. Processor extracts text content
4. Text is analyzed for PII
5. Results are written to output file

### Error Handling

Files that cannot be processed are logged with error information:
- Password-protected files
- Corrupted files
- Permission errors
- Unsupported formats (no processor available)

### Performance Considerations

- Large files are processed in chunks (PDFs)
- Text extraction is optimized for each format
- Unsupported files are skipped quickly
- Processing is multi-threaded for better performance

## Adding Support for New Formats

See the [Developer Documentation](../developer/adding-processors.md) for information on adding support for additional file formats.
