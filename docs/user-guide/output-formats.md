# Output Formats Documentation

## Overview

The PII Toolkit now supports three output formats for findings:
- **CSV** (default) - Comma-separated values
- **JSON** - Structured JSON format with metadata
- **XLSX** - Excel spreadsheet format

## Usage

### CSV Format (Default)

```bash
python main.py scan /data --regex
# or explicitly
python main.py scan /data --regex --format csv
```

**Output**: `[timestamp]_findings.csv`

**Format**:
```csv
Match,File,Type,Score,Engine
user@example.com,/data/file1.pdf,REGEX_EMAIL,,regex
DE89370400440532013000,/data/file2.docx,REGEX_IBAN,,regex
Max Mustermann,/data/file3.txt,NER_PERSON,0.85,gliner
```

**Features**:
- Header row included by default (can be disabled with `--no-header`)
- UTF-8 encoding
- Compatible with Excel, LibreOffice, and most CSV readers

### JSON Format

```bash
python main.py scan /data --regex --format json
```

**Output**: `[timestamp]_findings.json`

**Format**:
```json
{
  "metadata": {
    "start_time": "2024-01-15T10:30:00.123456",
    "end_time": "2024-01-15T10:30:05.789012",
    "duration_seconds": 5.665556,
    "path": "/data",
    "methods": {
      "regex": true,
      "ner": false,
      "spacy_ner": false,
      "ollama": true,
      "openai_compatible": false,
      "multimodal": false,
      "pydantic_ai": false
    },
    "total_files": 1234,
    "analyzed_files": 567,
    "matches_found": 89,
    "error_count": 12,
    "statistics": {
      "files_scanned": 1234,
      "files_analyzed": 567,
      "matches_found": 89,
      "errors": 12,
      "throughput_files_per_sec": 113.4
    },
    "file_extensions": {
      ".pdf": 42,
      ".docx": 23,
      ".html": 15,
      ".txt": 487
    },
    "errors": [
      {
        "type": "Permission denied",
        "files": ["/data/file1.pdf", "/data/file2.docx"]
      }
    ]
  },
  "findings": [
    {
      "text": "user@example.com",
      "file": "/data/file1.pdf",
      "type": "REGEX_EMAIL",
      "score": null,
      "engine": "regex",
      "metadata": {}
    },
    {
      "text": "DE89370400440532013000",
      "file": "/data/file2.docx",
      "type": "REGEX_IBAN",
      "score": null,
      "engine": "regex",
      "metadata": {}
    },
    {
      "text": "Max Mustermann",
      "file": "/data/file3.txt",
      "type": "NER_PERSON",
      "score": 0.85,
      "engine": "gliner",
      "metadata": {"gliner_label": "Person's Name"}
    }
  ]
}
```

**Features**:
- Structured data with metadata
- Includes statistics and error information
- Easy to parse programmatically
- UTF-8 encoding with proper Unicode support

### Excel Format (XLSX)

```bash
python main.py scan /data --regex --format xlsx
```

**Output**: `[timestamp]_findings.xlsx`

**Format**:
- Excel workbook with one sheet named "Findings"
- Optional second sheet named "Metadata" (top-level metadata key/value pairs)
- No styling is applied by default

**Columns**:
1. Match - The found PII text
2. File - Path to the file containing the match
3. Type - PII type (e.g. `REGEX_EMAIL`, `NER_PERSON`)
4. Score - Confidence score for AI-based matches (empty for regex matches)
5. Engine - Engine name (e.g. `regex`, `gliner`, `spacy-ner`, `pydantic-ai`)

**Features**:
- Compatible with Microsoft Excel, LibreOffice Calc, and Google Sheets
- UTF-8 encoding support

**Requirements**:
- `openpyxl` library (install via `pip install openpyxl` or `pip install -e ".[office]"`)

## Format Comparison

| Feature | CSV | JSON | XLSX |
|---------|-----|------|------|
| Human-readable | ✅ | ⚠️ | ✅ |
| Machine-readable | ⚠️ | ✅ | ⚠️ |
| Metadata included | ❌ | ✅ | ✅ (separate sheet) |
| Statistics included | ❌ | ✅ (inside metadata) | ✅ (inside metadata sheet) |
| Error information | ❌ | ✅ (inside metadata) | ✅ (inside metadata sheet) |
| Styled formatting | ❌ | ❌ | ❌ |
| File size | Small | Medium | Medium |
| Processing speed | Fast | Fast | Medium |

## Examples

### Basic Usage

```bash
# CSV (default)
python main.py scan /data --regex

# JSON
python main.py scan /data --regex --format json

# Excel
python main.py scan /data --regex --format xlsx
```

### With Custom Output Directory

```bash
python main.py scan /data --regex --format json --output-dir ./results/
```

### With Custom Output Name

```bash
python main.py scan /data --regex --format xlsx --outname "leak-2024"
# Output: 2024-01-15 10-30-00 leak-2024_findings.xlsx
```

### Full Example

```bash
python main.py \
  scan /var/data-leak/ \
  --regex \
  --ner \
  --format json \
  --outname "Großes Datenleck" \
  --whitelist stopwords.txt \
  --output-dir ./results/ \
  --verbose
```

## Implementation Details

### CSV Format
- Written incrementally during processing
- Header written at start (unless `--no-header`)
- Each match written immediately when found
- File remains open during entire analysis

### JSON Format
- Matches collected in memory during processing
- Complete JSON structure written at end
- Includes metadata (including statistics and errors) inside the `metadata` object
- Pretty-printed with 2-space indentation

### Excel Format
- Matches collected in memory during processing
- Excel file created at end with all matches
- Optional second "Metadata" sheet is written if metadata is present

## Backward Compatibility

- **CSV remains the default format** - existing scripts work without changes
- All existing CLI options work with all formats
- `--no-header` only affects CSV format
- Output file naming follows same pattern for all formats

## Error Handling

### Missing openpyxl for Excel Format

If `openpyxl` is not installed and Excel format is requested:
- The run fails during output finalization with an error

To install:
```bash
pip install openpyxl
```

## Performance Considerations

- **CSV**: Fastest, writes incrementally, low memory usage
- **JSON**: Fast, writes at end, moderate memory usage (all matches in memory)
- **XLSX**: Slower, writes at end, moderate memory usage (all matches in memory)

For very large result sets (>100k matches), CSV format is recommended for best performance.
