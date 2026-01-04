# Quick Start Guide

This guide will help you get started with the PII Toolkit in just a few minutes.

## Basic Usage

The simplest command to scan a directory:

```bash
python main.py scan /path/to/directory --regex
```

This will:
- Scan all files in the specified directory and subdirectories
- Use regular expression-based detection
- Create output files in the `./output/` directory

## Common Use Cases

### 1. Scan with Both Methods

Use both regex and AI-based detection:

```bash
python main.py scan /data --regex --ner
```

### 2. Custom Output Name

Add a custom name to output files:

```bash
python main.py scan /data --regex --outname "leak-analysis-2024"
```

Output files will be named: `2024-01-15 10-30-00 leak-analysis-2024_findings.csv`

### 3. Use Whitelist

Filter out known false positives:

```bash
python main.py scan /data --regex --whitelist stopwords.txt
```

The whitelist file should contain one string per line that will be matched against findings.

### 4. JSON Output

Get structured JSON output with metadata:

```bash
python main.py scan /data --regex --format json
```

### 5. Excel Output

Generate an Excel spreadsheet:

```bash
python main.py scan /data --regex --format xlsx
```

### 6. Test Run (Limited Files)

Test with a limited number of files:

```bash
python main.py scan /data --regex --stop-count 100
```

### 7. Verbose Mode

Get detailed logging and progress information:

```bash
python main.py scan /data --regex --verbose
```

### 8. Performance Modes

Tune the speed/stability trade-off depending on your workload:

```bash
# Safe: minimal resources (recommended for model-heavy scans)
python main.py scan /data --ner --mode safe

# Fast: higher parallelism (recommended for regex-heavy scans on many small files)
python main.py scan /data --regex --mode fast
```

## Complete Example

A comprehensive example with all options:

```bash
python main.py \
  scan /var/data-leak/ \
  --regex \
  --ner \
  --format json \
  --outname "comprehensive-scan" \
  --whitelist ./whitelist.txt \
  --output-dir ./results/ \
  --verbose
```

## Understanding the Output

After running the tool, you'll find:

1. **Findings File**: `[timestamp]_findings.[csv|json|jsonl|xlsx]`
   - Contains all detected PII matches
   - Includes file path, match type, and confidence scores

2. **Log File**: `[timestamp]_log.txt`
   - Contains execution details
   - Lists file extensions found
   - Reports errors and warnings

3. **Console Summary**: 
   - Quick overview of statistics
   - Performance metrics
   - Error summary

## Next Steps

- Read the [Command Line Interface documentation](../user-guide/cli.md) for all available options
- Learn about [Output Formats](../user-guide/output-formats.md)
- Explore [Supported File Formats](../user-guide/file-formats.md)
- Understand [PII Detection Methods](../user-guide/detection-methods.md)
