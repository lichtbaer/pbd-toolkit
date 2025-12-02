# CLI Options and Output Analysis

## Current CLI Options

### Required Options
- `--path`: Root directory to search recursively (required)

### Optional Options
- `--regex`: Enable regex-based PII detection (at least one of `--regex`/`--ner` required)
- `--ner`: Enable AI-based Named Entity Recognition (at least one of `--regex`/`--ner` required)
- `--verbose` / `-v`: Enable verbose output with detailed logging
- `--outname`: String to include in output file names
- `--whitelist`: Path to text file with exclusion patterns (one per line)
- `--stop-count`: Stop analysis after N files (for testing)

## Current Output Format

### Console Output (only in verbose mode)
```
Analysis
====================
Analysis started at [timestamp]

Regex-based search is active/not active.
AI-based search is active/not active.

Statistics
----------
The following file extensions have been found:
    [extension]: [count] Dateien
TOTAL: [count] files.
QUALIFIED: [count] files (supported file extension)

Findings
--------
--> see *_findings.csv

Errors
------
    [error_type]
        [file_path]

Analysis finished at [timestamp]
Performance of analysis: [files/sec] analyzed files per second
```

### File Outputs
1. **Log File**: `[timestamp]_log.txt` (or `[timestamp] [outname]_log.txt`)
   - Contains all logging information
   - Includes timestamps, log levels, messages
   - Only written to file (console only in verbose mode)

2. **CSV File**: `[timestamp]_findings.csv` (or `[timestamp] [outname]_findings.csv`)
   - Columns: `match`, `file`, `type`, `ner_score`
   - UTF-8 encoded
   - No header row currently

## Improvement Suggestions

### 1. CLI Options Improvements

#### 1.1 Add `--help` / `-h` Documentation
**Current State**: Basic argparse help exists but could be enhanced
**Suggestion**: 
- Add more detailed descriptions
- Include examples in help text
- Add usage examples section

#### 1.2 Add `--version` / `-V` Option
**Suggestion**: Display version information
```python
parser.add_argument("--version", "-V", action="version", version="%(prog)s 1.0.0")
```

#### 1.3 Add `--config` Option
**Suggestion**: Allow specifying custom config file path
```python
parser.add_argument("--config", action="store", default="config_types.json",
                    help="Path to configuration file (default: config_types.json)")
```

#### 1.4 Add `--output-dir` Option
**Suggestion**: Allow custom output directory
```python
parser.add_argument("--output-dir", action="store", default="./output/",
                    help="Directory for output files (default: ./output/)")
```

#### 1.5 Add `--max-file-size` Option
**Suggestion**: Allow configuring max file size limit
```python
parser.add_argument("--max-file-size", action="store", type=float, default=500.0,
                    help="Maximum file size in MB (default: 500.0)")
```

#### 1.6 Add `--threads` / `--workers` Option
**Suggestion**: Allow configuring parallel processing (if implemented)
```python
parser.add_argument("--threads", action="store", type=int, default=1,
                    help="Number of parallel workers (default: 1)")
```

#### 1.7 Add `--quiet` / `-q` Option
**Suggestion**: Suppress all non-error output (opposite of verbose)
```python
parser.add_argument("--quiet", "-q", action="store_true",
                    help="Suppress all output except errors")
```

#### 1.8 Improve Argument Validation
**Suggestion**: 
- Validate that at least one of `--regex`/`--ner` is set (currently done in code, but could be in argparse)
- Validate `--path` exists and is readable (currently done in code)
- Validate `--whitelist` file exists if provided
- Validate `--stop-count` is positive if provided

#### 1.9 Add `--format` Option for Output
**Suggestion**: Allow different output formats (JSON, XML, etc.)
```python
parser.add_argument("--format", choices=["csv", "json", "xml"], default="csv",
                    help="Output format for findings (default: csv)")
```

### 2. Output Format Improvements

#### 2.1 CSV File Improvements

**Current Issues**:
- No header row in CSV
- Column order: `match`, `file`, `type`, `ner_score`

**Suggestions**:
- **Add header row** (backward compatible by making it optional with `--no-header` flag)
  ```csv
  match,file,type,ner_score
  ```
- **Add summary row** at the end (optional with `--summary` flag)
- **Add timestamp column** to track when each match was found
- **Add line number column** (if possible) to show where in file match was found
- **Add context column** (optional) showing surrounding text

**Backward Compatibility**: 
- Default: Add header row (most CSV readers handle this)
- Add `--no-header` flag for strict backward compatibility
- Or: Add header only if `--format csv-with-header` is used

#### 2.2 Log File Improvements

**Current State**: Good, but could be enhanced

**Suggestions**:
- Add machine-readable JSON log option (`--log-format json`)
- Add structured logging with log levels
- Add performance metrics section
- Add configuration summary at start
- Add memory usage statistics (if available)

#### 2.3 Console Output Improvements

**Current Issues**:
- Only visible in verbose mode
- Mixed German/English (depends on LANGUAGE env var)
- No progress indication in non-verbose mode

**Suggestions**:
- **Always show summary** (even without verbose)
  - Total files processed
  - Total matches found
  - Total errors
  - Execution time
- **Progress bar** (already implemented, but could be improved)
  - Show in non-verbose mode for long operations
  - Add ETA (estimated time remaining)
  - Add throughput (MB/s, files/s)
- **Color output** (optional with `--color` flag)
  - Green for success
  - Yellow for warnings
  - Red for errors
- **Structured summary** at end:
  ```
  ========================================
  Analysis Summary
  ========================================
  Files processed:    1,234
  Files analyzed:     567
  Matches found:      89
  Errors:             12
  Execution time:     2m 34s
  Throughput:         3.7 files/sec
  ========================================
  ```

#### 2.4 Additional Output Formats

**Suggestions**:
- **JSON output** (`--format json`):
  ```json
  {
    "metadata": {
      "start_time": "2024-01-01T12:00:00",
      "end_time": "2024-01-01T12:05:00",
      "path": "/data",
      "config": {...}
    },
    "statistics": {
      "total_files": 1234,
      "analyzed_files": 567,
      "matches": 89,
      "errors": 12
    },
    "findings": [...],
    "errors": [...]
  }
  ```

- **XML output** (`--format xml`)
- **HTML report** (`--format html`) with:
  - Summary dashboard
  - Interactive file browser
  - Match highlighting
  - Charts/graphs

#### 2.5 Error Output Improvements

**Current State**: Errors listed at end

**Suggestions**:
- **Error summary** with counts per error type
- **Error file** separate from log (`*_errors.txt` or `*_errors.json`)
- **Error categorization**:
  - Critical (path traversal, permission denied)
  - Warnings (file too large, unsupported format)
  - Info (skipped files)

### 3. Compatibility Considerations

#### 3.1 Backward Compatibility Strategy

**Principle**: Maintain current output format as default, add new formats as options

**Implementation**:
1. **CSV Header**: 
   - Default: Add header (most tools handle this)
   - Flag: `--no-header` for strict compatibility
   - Or: Detect if output is piped/redirected and add header only then

2. **Output Location**:
   - Keep default `./output/` directory
   - Allow override with `--output-dir`

3. **Output Naming**:
   - Keep current timestamp-based naming
   - Keep `--outname` functionality

4. **Column Order**:
   - Never change existing column order
   - Only add new columns at the end

5. **Log Format**:
   - Keep current log format as default
   - Add new formats as options

#### 3.2 Migration Path

**Phase 1** (Immediate - Backward Compatible):
- Add CSV header (with `--no-header` flag for compatibility)
- Add summary to console (always, not just verbose)
- Add `--version` flag
- Add `--config` flag
- Add `--output-dir` flag

**Phase 2** (Future - Optional):
- Add JSON/XML output formats
- Add HTML report
- Add structured logging
- Add color output

### 4. Implementation Priority

#### High Priority (Easy wins, high impact)
1. ✅ Add CSV header row (with `--no-header` for compatibility)
2. ✅ Add `--version` flag
3. ✅ Add `--output-dir` flag
4. ✅ Always show summary (even without verbose)
5. ✅ Improve progress bar (show in non-verbose for long ops)

#### Medium Priority (Moderate effort, good UX)
1. Add `--config` flag
2. Add `--max-file-size` flag
3. Add error summary with counts
4. Add structured console summary
5. Add `--quiet` flag

#### Low Priority (Future enhancements)
1. Add JSON/XML output formats
2. Add HTML report
3. Add color output
4. Add context column to CSV
5. Add line numbers to matches

### 5. Code Changes Required

#### 5.1 Setup.py Changes
- Add new argument parsers
- Add validation logic
- Add version information

#### 5.2 Main.py Changes
- Modify CSV writing to include header
- Modify console output to always show summary
- Add output format selection logic

#### 5.3 Config.py Changes
- Add new configuration options
- Add validation for new options

### 6. Testing Considerations

- Test backward compatibility (old scripts should still work)
- Test new options in isolation
- Test output formats
- Test error handling for invalid options
- Test with different LANGUAGE settings

## Summary

The current CLI and output format are functional but could benefit from:
1. **Better usability**: More informative help, version info, better defaults
2. **Better output**: CSV headers, always-visible summary, structured formats
3. **More flexibility**: Custom output dirs, config files, output formats
4. **Better UX**: Progress indicators, color output, structured summaries

All improvements should maintain backward compatibility with existing scripts and workflows.
