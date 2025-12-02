# Command Line Interface

Complete reference for all command-line options.

## Required Arguments

### `--path` (Required)

Path to the root directory to scan recursively.

```bash
python main.py --path /var/data
```

**Note**: The tool will scan all subdirectories recursively.

## Analysis Methods

At least one of these must be specified:

### `--regex`

Enable regular expression-based pattern matching.

```bash
python main.py --path /data --regex
```

Detects:
- German pension insurance numbers
- IBAN (German bank accounts)
- Email addresses
- IPv4 addresses
- Signal words (German)
- Private PGP keys

### `--ner`

Enable AI-based Named Entity Recognition.

```bash
python main.py --path /data --ner
```

Detects:
- Person names
- Locations
- Health data (experimental)
- Passwords (experimental)

**Note**: Requires the GLiNER model to be downloaded (see [Installation](../getting-started/installation.md)).

## Optional Arguments

### `--outname`

Custom string to include in output file names.

```bash
python main.py --path /data --regex --outname "scan-2024"
```

Output: `2024-01-15 10-30-00 scan-2024_findings.csv`

### `--whitelist`

Path to a text file containing exclusion patterns (one per line).

```bash
python main.py --path /data --regex --whitelist stopwords.txt
```

Example `stopwords.txt`:
```
info@
noreply@
example.com
```

Any finding containing these strings will be excluded from output.

### `--stop-count`

Stop analysis after processing N files (useful for testing).

```bash
python main.py --path /data --regex --stop-count 100
```

### `--output-dir`

Directory for output files (default: `./output/`).

```bash
python main.py --path /data --regex --output-dir ./results/
```

### `--format`

Output format for findings (default: `csv`).

Options:
- `csv`: Comma-separated values
- `json`: JSON with metadata
- `xlsx`: Excel spreadsheet

```bash
python main.py --path /data --regex --format json
```

### `--no-header`

Don't include header row in CSV output (for backward compatibility).

```bash
python main.py --path /data --regex --no-header
```

### `--verbose`, `-v`

Enable verbose output with detailed logging and progress bar.

```bash
python main.py --path /data --regex --verbose
```

Includes:
- Detailed file processing information
- Progress bar
- Debug messages
- Console output in addition to log file

### `--version`, `-V`

Display version information and exit.

```bash
python main.py --version
```

## Environment Variables

### `LANGUAGE`

Set interface language: `de` (German, default) or `en` (English).

```bash
LANGUAGE=en python main.py --path /data --regex
```

## Examples

### Basic Scan

```bash
python main.py --path /var/data-leak --regex
```

### Full Featured Scan

```bash
python main.py \
  --path /var/data-leak/ \
  --regex \
  --ner \
  --format json \
  --outname "comprehensive-analysis" \
  --whitelist ./whitelist.txt \
  --output-dir ./results/ \
  --verbose
```

### Quick Test

```bash
python main.py --path /data --regex --stop-count 50 --verbose
```

### English Interface

```bash
LANGUAGE=en python main.py --path /data --regex --ner
```

## Output

The tool generates:

1. **Findings File**: `[timestamp]_findings.[format]`
   - All detected PII matches
   - Format depends on `--format` option

2. **Log File**: `[timestamp]_log.txt`
   - Execution details
   - File statistics
   - Errors and warnings

3. **Console Summary** (always shown):
   - Quick statistics
   - Performance metrics
   - Error summary

## Exit Codes

- `0`: Success
- `1`: Error (configuration, validation, or runtime error)

## Getting Help

Display help message:

```bash
python main.py --help
```
