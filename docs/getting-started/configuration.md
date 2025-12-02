# Configuration

The PII Toolkit can be configured through command-line arguments and configuration files.

## Command-Line Configuration

All configuration is done via command-line arguments. See the [CLI documentation](../user-guide/cli.md) for complete details.

## Configuration File: `config_types.json`

The `config_types.json` file controls which PII types are detected and how they are matched.

### Structure

The configuration file contains:

- **Settings**: Global configuration options
- **Regex**: Regular expression patterns for pattern matching
- **AI-NER**: Labels for AI-based Named Entity Recognition

### Settings

```json
{
  "settings": {
    "ner_threshold": 0.5,
    "min_pdf_text_length": 10,
    "max_file_size_mb": 500.0,
    "max_processing_time_seconds": 300,
    "supported_extensions": [".pdf", ".docx", ".html", ".txt", ...],
    "logging": {
      "level": "INFO",
      "format": "detailed"
    }
  }
}
```

### Regex Patterns

Each regex pattern defines:

- `label`: Internal identifier (e.g., `REGEX_EMAIL`)
- `value`: Display name in output (e.g., `"Regex: Email address"`)
- `regex_compiled_pos`: Position in compiled regex (0-based index)
- `expression`: The regular expression pattern

Example:

```json
{
  "label": "REGEX_EMAIL",
  "value": "Regex: Email address",
  "regex_compiled_pos": 2,
  "expression": "\\b[\\w\\-\\.]+@(?:[\\w+\\-]+\\.)+\\w{2,10}\\b"
}
```

### AI-NER Labels

Each NER label defines:

- `label`: Internal identifier (e.g., `NER_PERSON`)
- `value`: Display name in output (e.g., `"AI-NER: Person"`)
- `term`: Term used by the AI model for matching

Example:

```json
{
  "label": "NER_PERSON",
  "value": "AI-NER: Person",
  "term": "Person's Name"
}
```

## Environment Variables

### LANGUAGE

Set the interface language:

```bash
export LANGUAGE=en  # English
export LANGUAGE=de  # German (default)
```

Usage:

```bash
LANGUAGE=en python main.py --path /data --regex
```

## Default Values

### Output Directory

- Default: `./output/`
- Override with: `--output-dir /path/to/output`

### Output Format

- Default: `csv`
- Options: `csv`, `json`, `xlsx`
- Override with: `--format json`

### NER Threshold

- Default: `0.5` (from `config_types.json`)
- Controls minimum confidence for AI-based matches

### File Size Limit

- Default: `500 MB` (from `config_types.json`)
- Files larger than this are skipped

## Customizing Detection

### Adding New Regex Patterns

1. Edit `config_types.json`
2. Add a new entry to the `regex` array
3. Ensure `regex_compiled_pos` is unique and sequential
4. Test your pattern

### Modifying NER Labels

1. Edit `config_types.json`
2. Modify entries in the `ai-ner` array
3. Ensure `term` values match what the GLiNER model expects
4. Test with `--ner` flag

## Best Practices

1. **Backup Configuration**: Always backup `config_types.json` before making changes
2. **Test Changes**: Test regex patterns with a small dataset first
3. **Documentation**: Document any custom patterns you add
4. **Version Control**: Keep configuration files in version control
