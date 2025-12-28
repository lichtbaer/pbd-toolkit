# Output Formats Documentation

## Overview

The PII Toolkit now supports three output formats for findings:
- **CSV** (default) - Comma-separated values
- **JSON** - Structured JSON format with metadata
- **XLSX** - Excel spreadsheet format

## Usage

### CSV Format (Default)

```bash
python main.py --path /data --regex
# or explicitly
python main.py --path /data --regex --format csv
```

**Output**: `[timestamp]_findings.csv`

**Format**:
```csv
match,file,type,ner_score
user@example.com,/data/file1.pdf,Email,
DE89370400440532013000,/data/file2.docx,IBAN,
Max Mustermann,/data/file3.txt,Person Name,0.85
```

**Features**:
- Header row included by default (can be disabled with `--no-header`)
- UTF-8 encoding
- Compatible with Excel, LibreOffice, and most CSV readers

### JSON Format

```bash
python main.py --path /data --regex --format json
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
      "multimodal": false
    },
    "total_files": 1234,
    "analyzed_files": 567,
    "matches_found": 89,
    "errors": 12
  },
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
  "findings": [
    {
      "match": "user@example.com",
      "file": "/data/file1.pdf",
      "type": "Email",
      "ner_score": null
    },
    {
      "match": "DE89370400440532013000",
      "file": "/data/file2.docx",
      "type": "IBAN",
      "ner_score": null
    },
    {
      "match": "Max Mustermann",
      "file": "/data/file3.txt",
      "type": "Person Name",
      "ner_score": 0.85
    }
  ],
  "errors": [
    {
      "type": "Permission denied",
      "files": [
        "/data/file1.pdf",
        "/data/file2.docx"
      ]
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
python main.py --path /data --regex --format xlsx
```

**Output**: `[timestamp]_findings.xlsx`

**Format**:
- Excel workbook with one sheet named "Findings"
- Header row with styling (blue background, white bold text)
- Auto-adjusted column widths
- All data in a single sheet

**Columns**:
1. Match - The found PII text
2. File - Path to the file containing the match
3. Type - Type of PII (Email, IBAN, Person Name, etc.)
4. NER Score - Confidence score for AI-based matches (empty for regex matches)

**Features**:
- Professional formatting with styled headers
- Auto-adjusted column widths for readability
- Compatible with Microsoft Excel, LibreOffice Calc, and Google Sheets
- UTF-8 encoding support

**Requirements**:
- `openpyxl` library (install via `pip install -r requirements-dev.txt` or `pip install -e ".[office]"`)

## Format Comparison

| Feature | CSV | JSON | XLSX |
|---------|-----|------|------|
| Human-readable | ✅ | ⚠️ | ✅ |
| Machine-readable | ⚠️ | ✅ | ⚠️ |
| Metadata included | ❌ | ✅ | ❌ |
| Statistics included | ❌ | ✅ | ❌ |
| Error information | ❌ | ✅ | ❌ |
| Styled formatting | ❌ | ❌ | ✅ |
| File size | Small | Medium | Medium |
| Processing speed | Fast | Fast | Medium |

## Examples

### Basic Usage

```bash
# CSV (default)
python main.py --path /data --regex

# JSON
python main.py --path /data --regex --format json

# Excel
python main.py --path /data --regex --format xlsx
```

### With Custom Output Directory

```bash
python main.py --path /data --regex --format json --output-dir ./results/
```

### With Custom Output Name

```bash
python main.py --path /data --regex --format xlsx --outname "leak-2024"
# Output: 2024-01-15 10-30-00 leak-2024_findings.xlsx
```

### Full Example

```bash
python main.py \
  --path /var/data-leak/ \
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
- Includes all metadata, statistics, and errors
- Pretty-printed with 2-space indentation

### Excel Format
- Matches collected in memory during processing
- Excel file created at end with all matches
- Header row styled with blue background
- Column widths auto-adjusted for readability
- Falls back to CSV if `openpyxl` is not installed

## Backward Compatibility

- **CSV remains the default format** - existing scripts work without changes
- All existing CLI options work with all formats
- `--no-header` only affects CSV format
- Output file naming follows same pattern for all formats

## Error Handling

### Missing openpyxl for Excel Format

If `openpyxl` is not installed and Excel format is requested:
- Error message logged
- Automatically falls back to CSV format
- CSV file created with `.csv` extension instead of `.xlsx`

To install:
```bash
pip install openpyxl
# or
pip install -r requirements.txt
```

## Performance Considerations

- **CSV**: Fastest, writes incrementally, low memory usage
- **JSON**: Fast, writes at end, moderate memory usage (all matches in memory)
- **XLSX**: Slower, writes at end, moderate memory usage (all matches in memory)

For very large result sets (>100k matches), CSV format is recommended for best performance.
