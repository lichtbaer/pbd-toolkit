# File Format Evaluation for PII Detection

## Current Status

The toolkit currently supports the following file formats:
- `.pdf` - PDF documents
- `.docx` - Microsoft Word documents
- `.html` / `.htm` - HTML files
- `.txt` - Plain text files (including files without extension with mime type "text/plain")

## Evaluation Criteria

When evaluating new file formats, the following criteria are considered:
1. **Prevalence in data leaks** - How commonly are these formats found in leaked data?
2. **PII content likelihood** - How likely are these formats to contain personally identifiable information?
3. **Implementation complexity** - How difficult is it to extract text from these formats?
4. **Library availability** - Are reliable Python libraries available for processing?
5. **File size considerations** - Can these files be processed efficiently?

## Recommended File Formats (Priority Order)

### High Priority

#### 1. **XLSX / XLS (Excel Spreadsheets)**
- **Prevalence**: ⭐⭐⭐⭐⭐ Very common in business contexts and data leaks
- **PII Content**: ⭐⭐⭐⭐⭐ Extremely high - spreadsheets often contain databases of personal information
- **Implementation**: ⭐⭐⭐⭐ Moderate - well-established libraries available
- **Library**: `openpyxl` (for XLSX), `xlrd` (for XLS, older format)
- **Notes**: 
  - Excel files frequently contain structured personal data (names, addresses, phone numbers, etc.)
  - Should extract text from all cells, including multiple sheets
  - Consider handling formulas (extract calculated values, not formulas themselves)

#### 2. **CSV (Comma-Separated Values)**
- **Prevalence**: ⭐⭐⭐⭐⭐ Extremely common in data exports and leaks
- **PII Content**: ⭐⭐⭐⭐⭐ Very high - structured data format often used for personal information databases
- **Implementation**: ⭐⭐⭐⭐⭐ Very easy - Python's built-in `csv` module
- **Library**: Built-in `csv` module
- **Notes**:
  - Very common format for data dumps
  - Should handle different delimiters (comma, semicolon, tab)
  - Should handle different encodings
  - May need to handle quoted fields and escape sequences

#### 3. **RTF (Rich Text Format)**
- **Prevalence**: ⭐⭐⭐⭐ Common, especially in older documents
- **PII Content**: ⭐⭐⭐⭐ High - document format similar to DOCX
- **Implementation**: ⭐⭐⭐ Moderate
- **Library**: `striprtf` or `pyth` (RTF parser)
- **Notes**:
  - Older format but still widely used
  - Similar content to DOCX files
  - Text extraction is straightforward

#### 4. **ODT (OpenDocument Text)**
- **Prevalence**: ⭐⭐⭐ Moderate - open source alternative to DOCX
- **PII Content**: ⭐⭐⭐⭐ High - similar to DOCX
- **Implementation**: ⭐⭐⭐⭐ Easy - similar structure to DOCX
- **Library**: `odfpy` or `python-odf`
- **Notes**:
  - OpenDocument format (used by LibreOffice, OpenOffice)
  - Similar structure to DOCX (ZIP-based XML)
  - Should extract text from paragraphs, headers, footers, tables

#### 5. **MSG (Outlook Email Messages)**
- **Prevalence**: ⭐⭐⭐⭐ Common in email-related data leaks
- **PII Content**: ⭐⭐⭐⭐⭐ Very high - emails contain extensive personal information
- **Implementation**: ⭐⭐⭐ Moderate
- **Library**: `extract-msg` or `msg-parser`
- **Notes**:
  - Microsoft Outlook email format
  - Should extract: subject, body, sender, recipients, attachments metadata
  - May contain embedded attachments (which could be processed separately)

#### 6. **EML (Email Message Files)**
- **Prevalence**: ⭐⭐⭐⭐ Common in email exports
- **PII Content**: ⭐⭐⭐⭐⭐ Very high - standard email format
- **Implementation**: ⭐⭐⭐⭐ Easy - standard email format
- **Library**: Built-in `email` module
- **Notes**:
  - Standard email format (RFC 822)
  - Can use Python's built-in `email` module
  - Should extract: headers, body (plain text and HTML parts)

#### 7. **JSON (JavaScript Object Notation)**
- **Prevalence**: ⭐⭐⭐⭐⭐ Very common in modern data leaks and API dumps
- **PII Content**: ⭐⭐⭐⭐ High - structured data often contains personal information
- **Implementation**: ⭐⭐⭐⭐⭐ Very easy - built-in `json` module
- **Library**: Built-in `json` module
- **Notes**:
  - Very common in API responses and modern data formats
  - Should extract all string values (keys and values)
  - May need to handle nested structures
  - Consider handling large JSON files efficiently

### Medium Priority

#### 8. **XML (eXtensible Markup Language)**
- **Prevalence**: ⭐⭐⭐⭐ Common in structured data exports
- **PII Content**: ⭐⭐⭐⭐ High - structured format often used for personal data
- **Implementation**: ⭐⭐⭐⭐ Easy - built-in `xml.etree.ElementTree`
- **Library**: Built-in `xml.etree.ElementTree` or `lxml`
- **Notes**:
  - Should extract text from all elements and attributes
  - May need to handle namespaces
  - Consider handling large XML files (streaming parser)

#### 9. **PPTX / PPT (PowerPoint Presentations)**
- **Prevalence**: ⭐⭐⭐ Moderate - less common in data leaks but still relevant
- **PII Content**: ⭐⭐⭐ Moderate - presentations may contain personal information
- **Implementation**: ⭐⭐⭐ Moderate
- **Library**: `python-pptx` (for PPTX), `python-pptx` or `pywin32` (for PPT)
- **Notes**:
  - Should extract text from slides, notes, and comments
  - Less critical than Word/Excel but still useful

#### 10. **ODS (OpenDocument Spreadsheet)**
- **Prevalence**: ⭐⭐⭐ Moderate - open source alternative to Excel
- **PII Content**: ⭐⭐⭐⭐ High - similar to Excel
- **Implementation**: ⭐⭐⭐ Moderate
- **Library**: `odfpy` or `ezodf`
- **Notes**:
  - OpenDocument spreadsheet format
  - Similar to Excel in terms of PII content

#### 11. **YAML / YML**
- **Prevalence**: ⭐⭐⭐ Moderate - common in configuration files and some data exports
- **PII Content**: ⭐⭐⭐ Moderate - may contain personal information
- **Implementation**: ⭐⭐⭐⭐ Easy
- **Library**: `PyYAML`
- **Notes**:
  - Should extract all string values
  - Less common in data leaks but still useful

### Lower Priority

#### 12. **Markdown (.md, .markdown)**
- **Prevalence**: ⭐⭐ Low - mainly documentation
- **PII Content**: ⭐⭐ Low - mainly technical documentation
- **Implementation**: ⭐⭐⭐⭐⭐ Very easy - mostly plain text
- **Library**: Built-in (can be treated as text) or `markdown` for structured extraction
- **Notes**:
  - Can mostly be treated as plain text
  - Less likely to contain PII in data leaks

#### 13. **EPUB (eBook Format)**
- **Prevalence**: ⭐⭐ Low - mainly ebooks
- **PII Content**: ⭐⭐ Low - mainly published content
- **Implementation**: ⭐⭐⭐ Moderate
- **Library**: `ebooklib` or `zipfile` (EPUB is ZIP-based)
- **Notes**:
  - Less relevant for data leak analysis
  - Could be useful for completeness

## Implementation Recommendations

### Phase 1 (Immediate High Value)
1. **CSV** - Very easy to implement, extremely common
2. **JSON** - Very easy to implement, very common in modern data leaks
3. **XLSX** - High value, moderate complexity

### Phase 2 (High Value, Moderate Complexity)
4. **RTF** - Common format, moderate complexity
5. **ODT** - Similar to DOCX, good coverage
6. **EML** - Common email format, easy to implement

### Phase 3 (Specialized Formats)
7. **MSG** - Email format, requires specialized library
8. **XML** - Structured data, should handle large files
9. **PPTX** - Lower priority but still useful

### Phase 4 (Completeness)
10. **ODS** - Open source spreadsheet format
11. **YAML** - Configuration/data format
12. **Markdown** - Can be treated as text
13. **EPUB** - Lower priority

## Technical Considerations

### Library Dependencies
New formats will require additional dependencies. Consider:
- **openpyxl** - For XLSX files
- **xlrd** - For older XLS files (note: xlrd 2.0+ only supports .xls, not .xlsx)
- **striprtf** or **pyth** - For RTF files
- **odfpy** or **python-odf** - For ODT/ODS files
- **extract-msg** or **msg-parser** - For MSG files
- **PyYAML** - For YAML files
- **python-pptx** - For PPTX files

### Performance Considerations
- Some formats (especially spreadsheets) can be very large
- Consider streaming/chunked processing for large files
- CSV and JSON files can be very large - may need special handling
- XML files may need streaming parsers for large files

### Error Handling
- Some formats may be corrupted or password-protected
- Should handle encoding issues gracefully
- Should log unsupported or problematic files

## Summary

The most valuable additions would be:
1. **CSV** - Easy, extremely common, high PII content
2. **JSON** - Easy, very common in modern leaks, high PII content
3. **XLSX/XLS** - Moderate complexity, very common, extremely high PII content
4. **RTF** - Moderate complexity, common, high PII content
5. **EML/MSG** - Email formats, high PII content

These five formats would significantly expand the toolkit's coverage of common data leak scenarios while maintaining reasonable implementation complexity.
