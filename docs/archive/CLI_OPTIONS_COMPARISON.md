# CLI Options Comparison: Current vs. Proposed

## Current CLI Help Output (Example)

```
usage: HBDI PII Toolkit [-h] [--path PATH] [--outname OUTNAME] 
                         [--whitelist WHITELIST] [--stop-count STOP_COUNT]
                         [--regex] [--ner] [--verbose]

options:
  -h, --help            show this help message and exit
  --path PATH           Root directory under which to recursively search for PII
  --outname OUTNAME     Optional parameter; string which to include in the file name 
                        of all output files
  --whitelist WHITELIST Optional parameter; relative path to a text file containing 
                        one string per line. These strings will be matched against 
                        potential findings to exclude them from the output.
  --stop-count STOP_COUNT
                        Optional parameter; stop analysis after N files
  --regex               Use regular expressions for analysis
  --ner                 Use AI-based Named Entity Recognition for analysis
  --verbose, -v         Enable verbose output with detailed logging
```

## Proposed CLI Help Output

```
usage: HBDI PII Toolkit [-h] [--version] [--path PATH] [--regex] [--ner]
                        [--outname OUTNAME] [--whitelist WHITELIST]
                        [--stop-count STOP_COUNT] [--config CONFIG]
                        [--output-dir OUTPUT_DIR] [--max-file-size MAX_FILE_SIZE]
                        [--format {csv,json,xml}] [--no-header] [--quiet]
                        [--verbose, -v]

PII Detection Toolkit - Scan directories for personally identifiable information

Required Arguments:
  --path PATH           Root directory to recursively search for PII
                       (required)

Analysis Methods (at least one required):
  --regex               Enable regex-based PII detection
  --ner                 Enable AI-based Named Entity Recognition

Optional Arguments:
  --outname OUTNAME     String to include in output file names
  --whitelist WHITELIST Path to text file with exclusion patterns (one per line)
  --stop-count STOP_COUNT
                        Stop analysis after N files (for testing)
  --config CONFIG       Path to configuration file (default: config_types.json)
  --output-dir OUTPUT_DIR
                        Directory for output files (default: ./output/)
  --max-file-size MAX_FILE_SIZE
                        Maximum file size in MB (default: 500.0)

Output Options:
  --format {csv,json,xml}
                        Output format for findings (default: csv)
  --no-header           Don't include header row in CSV output
  --quiet, -q           Suppress all output except errors
  --verbose, -v         Enable verbose output with detailed logging

General Options:
  -h, --help            Show this help message and exit
  --version, -V         Show version information and exit

Examples:
  # Basic usage with regex
  python main.py --path /data --regex

  # Full analysis with custom output
  python main.py --path /data --regex --ner --outname "leak-2024" 
                 --whitelist exclude.txt --output-dir ./results/

  # Quick test run
  python main.py --path /data --regex --stop-count 100 --verbose

  # JSON output format
  python main.py --path /data --ner --format json --output-dir ./json_results/
```

## Current Output Example

### Console (verbose mode only)
```
2024-01-15 10:30:00 - INFO - Analysis
2024-01-15 10:30:00 - INFO - ====================
2024-01-15 10:30:00 - INFO - Analysis started at 2024-01-15 10:30:00.123456
2024-01-15 10:30:00 - INFO - Regex-based search is active.
2024-01-15 10:30:00 - INFO - AI-based search is active.
2024-01-15 10:30:00 - INFO - 
2024-01-15 10:30:05 - INFO - Statistics
2024-01-15 10:30:05 - INFO - ----------
2024-01-15 10:30:05 - INFO - The following file extensions have been found:
2024-01-15 10:30:05 - INFO -       .pdf:         42 Dateien
2024-01-15 10:30:05 - INFO -      .docx:         23 Dateien
2024-01-15 10:30:05 - INFO - TOTAL: 1234 files.
2024-01-15 10:30:05 - INFO - QUALIFIED: 567 files (supported file extension)
2024-01-15 10:30:05 - INFO - 
2024-01-15 10:30:05 - INFO - Findings
2024-01-15 10:30:05 - INFO - --------
2024-01-15 10:30:05 - INFO - --> see *_findings.csv
2024-01-15 10:30:05 - INFO - 
2024-01-15 10:30:05 - INFO - Errors
2024-01-15 10:30:05 - INFO - ------
2024-01-15 10:30:05 - INFO - 	Permission denied
2024-01-15 10:30:05 - INFO - 		/path/to/file1.pdf
2024-01-15 10:30:05 - INFO - 
2024-01-15 10:30:05 - INFO - Analysis finished at 2024-01-15 10:30:05.789012
2024-01-15 10:30:05 - INFO - Performance of analysis: 113.4 analyzed files per second
```

### CSV File (current - no header)
```csv
user@example.com,/data/file1.pdf,Email,
DE89370400440532013000,/data/file2.docx,IBAN,
Max Mustermann,/data/file3.txt,Person Name,0.85
```

## Proposed Output Example

### Console (always shown - improved summary)
```
========================================
HBDI PII Toolkit - Analysis Summary
========================================
Started:     2024-01-15 10:30:00
Finished:    2024-01-15 10:30:05
Duration:    5 seconds

Configuration:
  Search path:    /data
  Methods:        Regex, NER
  Output dir:     ./output/

Statistics:
  Files scanned:      1,234
  Files analyzed:     567
  Matches found:      89
  Errors:             12

Performance:
  Throughput:         113.4 files/sec
  Avg file size:      2.3 MB

File Extensions Found:
  .pdf:     42 files
  .docx:    23 files
  .html:    15 files
  .txt:     487 files

Errors Summary:
  Permission denied:       5 files
  File too large:          2 files
  Unicode decode error:    3 files
  Other:                   2 files

Output Files:
  Findings:  ./output/2024-01-15 10-30-00_findings.csv
  Log:       ./output/2024-01-15 10-30-00_log.txt

========================================
```

### CSV File (proposed - with header)
```csv
match,file,type,ner_score
user@example.com,/data/file1.pdf,Email,
DE89370400440532013000,/data/file2.docx,IBAN,
Max Mustermann,/data/file3.txt,Person Name,0.85
```

### JSON Output (proposed - with --format json)
```json
{
  "metadata": {
    "version": "1.0.0",
    "start_time": "2024-01-15T10:30:00",
    "end_time": "2024-01-15T10:30:05",
    "path": "/data",
    "methods": ["regex", "ner"],
    "config_file": "config_types.json"
  },
  "statistics": {
    "total_files": 1234,
    "analyzed_files": 567,
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
    }
  ],
  "errors": [
    {
      "type": "Permission denied",
      "files": ["/path/to/file1.pdf", "/path/to/file2.docx"]
    }
  ]
}
```

## Key Improvements Summary

### CLI Options
1. ✅ Better organization (grouped by function)
2. ✅ More descriptive help text
3. ✅ Examples section
4. ✅ Version information
5. ✅ More configuration options

### Output Format
1. ✅ CSV header row (with `--no-header` for compatibility)
2. ✅ Always-visible summary (not just verbose)
3. ✅ Structured, readable format
4. ✅ Error summary with counts
5. ✅ Performance metrics
6. ✅ Multiple output formats (CSV, JSON, XML)

### Backward Compatibility
- All current options work the same
- CSV format compatible (header can be disabled)
- Output location configurable but defaults to current
- All new features are opt-in
