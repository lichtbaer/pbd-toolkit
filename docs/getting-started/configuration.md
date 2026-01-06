# Configuration

The PII Toolkit can be configured through command-line arguments and configuration files (YAML or JSON).

## Command-Line Configuration

All configuration can be done via command-line arguments. See the [CLI documentation](../user-guide/cli.md) for complete details.

## Configuration Files

You can use a configuration file (YAML or JSON) to set default values, which can then be overridden by command-line arguments.

### Usage

```bash
python main.py scan /data --config config.yaml
```

**Note**: CLI arguments take precedence over config file values. The scan path can be provided as positional `<path>`, via `--path`, or inside the config file as `path: ...`.

### YAML Configuration File

Example `config.yaml`:

```yaml
path: "/path/to/scan"
regex: true
ner: true
spacy_ner: false
spacy_model: "de_core_news_lg"
ollama: false
ollama_url: "http://localhost:11434"
ollama_model: "llama3.2"
openai_compatible: false
openai_api_base: "https://api.openai.com/v1"
openai_api_key: null
openai_model: "gpt-3.5-turbo"

# Recommended unified LLM engine:
pydantic_ai: false
pydantic_ai_provider: "openai"
pydantic_ai_model: null
pydantic_ai_api_key: null
pydantic_ai_base_url: null

# Image detection (OpenAI-compatible vision endpoint):
multimodal: false
multimodal_api_base: null
multimodal_api_key: null
multimodal_model: "gpt-4o-mini"
multimodal_timeout: 60

# File type detection:
use_magic_detection: false
magic_fallback: true

format: "json"
verbose: false
output_dir: "./output/"
whitelist: "./whitelist.txt"
stop_count: 1000
mode: "balanced"
jobs: null
summary_format: "human"
no_header: false
quiet: false

# Privacy-focused statistics output:
statistics_mode: false
statistics_strict: false
statistics_output: null
```

### JSON Configuration File

Example `config.json`:

```json
{
  "path": "/path/to/scan",
  "regex": true,
  "ner": true,
  "spacy_ner": false,
  "ollama": false,
  "openai_compatible": false,
  "pydantic_ai": false,
  "multimodal": false,
  "format": "json",
  "verbose": false,
  "output_dir": "./output/",
  "whitelist": "./whitelist.txt",
  "stop_count": 1000
}
```

### Supported Configuration Options

All command-line arguments can be specified in the config file using their long form (without `--`):
- `path`, `regex`, `ner`, `spacy_ner`, `ollama`, `openai_compatible`
- `spacy_model`, `ollama_url`, `ollama_model`
- `openai_api_base`, `openai_api_key`, `openai_model`
- `multimodal`, `multimodal_api_base`, `multimodal_api_key`, `multimodal_model`, `multimodal_timeout`
- `pydantic_ai`, `pydantic_ai_provider`, `pydantic_ai_model`, `pydantic_ai_api_key`, `pydantic_ai_base_url`
- `use_magic_detection`, `magic_fallback`
- `outname`, `whitelist`, `stop_count`, `output_dir`, `format`
- `mode`, `jobs`
- `summary_format`, `no_header`, `verbose`, `quiet`
- `statistics_mode`, `statistics_strict`, `statistics_output`

See example files: `docs/CONFIG_FILE_EXAMPLE.yaml` and `docs/CONFIG_FILE_EXAMPLE.json`

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
LANGUAGE=en python main.py scan /data --regex
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
