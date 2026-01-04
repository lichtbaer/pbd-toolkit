# Command Line Interface

Complete reference for all command-line options.

## Command

### `scan [path]` / `scan --path <path>`

Path to the root directory to scan recursively. You can provide it:
- as a positional argument (`scan /data`)
- via `--path /data`
- or via a config file (`path: /data`) if neither positional nor `--path` is provided

```bash
python main.py scan /var/data
# or, after installation:
pii-toolkit scan /var/data
```

**Note**: The tool will scan all subdirectories recursively.

## Analysis Methods

At least one of these must be specified:

### `--regex`

Enable regular expression-based pattern matching.

```bash
python main.py scan /data --regex
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
python main.py scan /data --ner
```

Detects:
- Person names
- Locations
- Health data (experimental)
- Passwords (experimental)

**Note**: Requires the GLiNER model to be downloaded (see [Installation](../getting-started/installation.md)).

### `--spacy-ner`

Enable spaCy NER detection (optimized for German text).

```bash
python main.py scan /data --spacy-ner --spacy-model de_core_news_lg
```

**Options**:
- `--spacy-model`: Model to use (`de_core_news_sm`, `de_core_news_md`, `de_core_news_lg`)

**Note**: Requires spaCy and German model to be installed (see [Installation](../getting-started/installation.md)).

### `--ollama`

Enable Ollama LLM-based detection (local, offline).

```bash
python main.py scan /data --ollama --ollama-model llama3.2
```

**Options**:
- `--ollama-url`: Ollama API base URL (default: `http://localhost:11434`)
- `--ollama-model`: Model to use (default: `llama3.2`)

**Note**: Requires Ollama server to be running (see [Installation](../getting-started/installation.md)).

### `--openai-compatible`

Enable OpenAI-compatible API detection.

```bash
python main.py scan /data --openai-compatible \
    --openai-api-key YOUR_KEY \
    --openai-model gpt-3.5-turbo
```

**Options**:
- `--openai-api-base`: API base URL (default: `https://api.openai.com/v1`)
- `--openai-api-key`: API key (or set `OPENAI_API_KEY` environment variable)
- `--openai-model`: Model to use (default: `gpt-3.5-turbo`)

## Optional Arguments

### `--mode`

Execution mode controlling the speed/stability trade-off (default: `balanced`).

**Options:**
- `safe`: Minimal resource usage (single worker). Recommended for model-heavy scans (GLiNER/LLM) on constrained machines.
- `balanced`: Reasonable throughput with conservative engine locking (default).
- `fast`: Higher parallelism for maximum throughput (best for many small files + regex-heavy workloads).

```bash
python main.py scan /data --regex --mode fast
python main.py scan /data --ner --mode safe
```

### `--jobs`

Number of parallel file workers. Overrides `--mode`.

```bash
python main.py scan /data --regex --jobs 8
```

### `--outname`

Custom string to include in output file names.

```bash
python main.py scan /data --regex --outname "scan-2024"
```

Output: `2024-01-15 10-30-00 scan-2024_findings.csv`

### `--whitelist`

Path to a text file containing exclusion patterns (one per line).

```bash
python main.py scan /data --regex --whitelist stopwords.txt
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
python main.py scan /data --regex --stop-count 100
```

**Note**: The count refers to files that are eligible for analysis (supported file types), not every file encountered on disk.

### `--output-dir`

Directory for output files (default: `./output/`).

```bash
python main.py scan /data --regex --output-dir ./results/
```

### `--format`

Output format for findings (default: `csv`).

Options:
- `csv`: Comma-separated values
- `json`: JSON with metadata
- `xlsx`: Excel spreadsheet

```bash
python main.py scan /data --regex --format json
```

### `--no-header`

Don't include header row in CSV output (for backward compatibility).

```bash
python main.py scan /data --regex --no-header
```

### `--verbose`, `-v`

Enable verbose output with detailed logging and progress bar.

```bash
python main.py scan /data --regex --verbose
```

Includes:
- Detailed file processing information
- Progress bar (exact total is only shown if progress estimation is enabled; see `PII_TOOLKIT_PROGRESS_ESTIMATE`)
- Debug messages
- Console output in addition to log file

### `--quiet`, `-q`

Suppress all output except errors. Useful for automation and scripts where only errors are relevant.

```bash
python main.py scan /data --regex --quiet
```

**Note**: When `--quiet` is specified:
- Only error messages are shown to console
- Summary output is suppressed
- Log file still contains all information
- Exit codes are still returned for automation

### Version

Show the installed package version:

```bash
pii-toolkit --version
# or
pii-toolkit -V
```

### `--config`

Path to configuration file (YAML or JSON). CLI arguments override config file values.

```bash
python main.py scan /data --config config.yaml
```

**Example config.yaml:**
```yaml
regex: true
ner: true
format: "json"
verbose: false
```

**Example config.json:**
```json
{
  "regex": true,
  "ner": true,
  "format": "json"
}
```

**Note**: CLI arguments take precedence over config file values. The scan path can be provided as positional `<path>`, via `--path`, or inside the config file as `path: ...`.

### `--summary-format`

Format for summary output. Use `json` for machine-readable output.

```bash
python main.py scan /data --regex --summary-format json
```

**Options:**
- `human` (default): Human-readable text output
- `json`: Machine-readable JSON output

**Example JSON output:**
```json
{
  "start_time": "2024-01-01T10:00:00",
  "end_time": "2024-01-01T10:05:00",
  "duration_seconds": 300.0,
  "statistics": {
    "files_scanned": 1000,
    "files_analyzed": 950,
    "matches_found": 42,
    "errors": 2,
    "throughput_files_per_sec": 3.17
  },
  "output_file": "./output/2024-01-01 10-00-00_findings.csv",
  "output_directory": "./output/",
  "errors_summary": {
    "Permission denied": 2
  }
}
```

## Environment Variables

### `LANGUAGE`

Set interface language: `de` (German, default) or `en` (English).

```bash
LANGUAGE=en python main.py scan /data --regex
```

### `PII_TOOLKIT_PROGRESS_ESTIMATE`

Enable a pre-scan pass to estimate the total number of files for an exact progress bar total.

**Note**: This may significantly increase runtime on large directory trees because it performs an additional directory walk.

```bash
PII_TOOLKIT_PROGRESS_ESTIMATE=1 python main.py scan /data --regex --verbose
```

## Examples

### Basic Scan

```bash
python main.py scan /var/data-leak --regex
```

### Full Featured Scan

```bash
python main.py \
  scan /var/data-leak/ \
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
python main.py scan /data --regex --stop-count 50 --verbose
```

### English Interface

```bash
LANGUAGE=en python main.py scan /data --regex --ner
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

The tool uses standardized exit codes for automation and scripting:

- `0` (`EXIT_SUCCESS`): Analysis completed successfully
- `1` (`EXIT_GENERAL_ERROR`): General error occurred
- `2` (`EXIT_INVALID_ARGUMENTS`): Invalid command-line arguments
- `3` (`EXIT_FILE_ACCESS_ERROR`): File access error (reserved for future use)
- `4` (`EXIT_CONFIGURATION_ERROR`): Configuration error or NER model loading failed

See [Exit Codes Documentation](../EXIT_CODES.md) for detailed information and usage examples.

## Getting Help

Display help message:

```bash
python main.py --help
```
