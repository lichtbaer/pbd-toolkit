# Configuration System

This document describes the configuration system used by the PII Toolkit.

## Overview

The configuration system manages:
- Command-line argument parsing
- NER model loading and initialization
- Regex pattern compilation
- Logging setup
- Output file handling

## Configuration Class

**File**: `config.py`

The `Config` class is the central configuration object:

```python
from config import Config

config = Config.from_args(
    args=globals.args,
    logger=globals.logger,
    csv_writer=globals.csvwriter,
    csv_file_handle=globals.csv_file_handle,
    translate_func=globals._
)
```

## Configuration Sources

### 1. Command-Line Arguments

Parsed by `setup.py` using `argparse`:

- `--path`: Root directory to scan
- `--regex`: Enable regex detection
- `--ner`: Enable NER detection
- `--outname`: Custom output name
- `--whitelist`: Whitelist file path
- `--stop-count`: Limit number of files
- `--output-dir`: Output directory
- `--format`: Output format (csv/json/xlsx)
- `--verbose`: Verbose logging

### 2. Configuration File

**File**: `config_types.json`

JSON file containing:
- Settings (thresholds, limits, etc.)
- Regex patterns
- NER labels

### 3. Environment Variables

- `LANGUAGE`: Interface language (de/en)

### 4. Constants

**File**: `constants.py`

Application-wide constants:
- `NER_MODEL_NAME`: Model identifier
- `NER_THRESHOLD`: Default confidence threshold
- `OUTPUT_DIR`: Default output directory
- `CONFIG_FILE`: Configuration file path

## Configuration File Structure

### Settings

```json
{
  "settings": {
    "ner_threshold": 0.5,
    "min_pdf_text_length": 10,
    "max_file_size_mb": 500.0,
    "max_processing_time_seconds": 300,
    "supported_extensions": [".pdf", ".docx", ...],
    "logging": {
      "level": "INFO",
      "format": "detailed"
    }
  }
}
```

### Regex Patterns

```json
{
  "regex": [
    {
      "label": "REGEX_EMAIL",
      "value": "Regex: Email address",
      "regex_compiled_pos": 2,
      "expression": "\\b[\\w\\-\\.]+@(?:[\\w+\\-]+\\.)+\\w{2,10}\\b"
    }
  ]
}
```

### NER Labels

```json
{
  "ai-ner": [
    {
      "label": "NER_PERSON",
      "value": "AI-NER: Person",
      "term": "Person's Name"
    }
  ]
}
```

## Configuration Loading

### Initialization Flow

1. **Setup Phase** (`setup.py`):
   - Parse command-line arguments
   - Setup internationalization
   - Setup logging
   - Create output files

2. **Config Creation** (`config.py`):
   - Load `config_types.json`
   - Compile regex patterns
   - Load NER model (if enabled)
   - Validate configuration

### Regex Compilation

Regex patterns are compiled into a single pattern:

```python
patterns = [r"pattern1", r"pattern2", ...]
combined_pattern = "|".join(f"({p})" for p in patterns)
compiled_regex = re.compile(combined_pattern, re.IGNORECASE)
```

Matches are identified by their group number (corresponding to `regex_compiled_pos`).

### NER Model Loading

The GLiNER model is loaded on-demand:

```python
if use_ner:
    from gliner import GLiNER
    model = GLiNER.from_pretrained("urchade/gliner_medium-v2.1")
```

Model loading can fail if:
- Model not downloaded
- Insufficient memory
- Network issues (if downloading)

## Configuration Validation

### Path Validation

```python
def validate_path(self) -> tuple[bool, Optional[str]]:
    """Validate the search path."""
    if not os.path.exists(self.path):
        return False, "Path does not exist"
    if not os.path.isdir(self.path):
        return False, "Path is not a directory"
    return True, None
```

### File Path Validation

```python
def validate_file_path(self, file_path: str) -> tuple[bool, Optional[str]]:
    """Validate file path (security check)."""
    # Check for path traversal
    # Check file size
    # Return validation result
```

## Accessing Configuration

### In Main Code

```python
from config import Config

config = create_config()  # From setup.py

# Access configuration
if config.use_regex:
    # Use regex detection
    pass

if config.use_ner:
    # Use NER detection
    entities = config.ner_model.predict_entities(...)
```

### In Processors

Configuration is passed as a parameter:

```python
def process_text(text: str, file_path: str, pmc: PiiMatchContainer, config: Config):
    if config.use_regex:
        # Process with regex
        pass
```

## Internationalization

Configuration supports multiple languages:

```python
config._("Error message")  # Translated string
```

Translation files are in `locales/` directory.

## Logging Configuration

Logging is configured in `setup.py`:

```python
def __setup_logger(outslug: str = "") -> None:
    log_level = logging.DEBUG if verbose else logging.INFO
    # Setup file and console handlers
```

## Extending Configuration

### Adding New Settings

1. Add to `config_types.json`:
```json
{
  "settings": {
    "new_setting": "value"
  }
}
```

2. Access in `Config` class:
```python
self.new_setting = settings.get("new_setting", default_value)
```

### Adding CLI Options

1. Add to `setup.py`:
```python
parser.add_argument("--new-option", action="store", help="...")
```

2. Access via `args`:
```python
config.new_option = args.new_option
```

## Best Practices

1. **Validation**: Always validate user input
2. **Defaults**: Provide sensible defaults
3. **Error Messages**: Use translated error messages
4. **Type Safety**: Use type hints
5. **Documentation**: Document all configuration options

## Testing Configuration

Test configuration loading:

```python
def test_config_loading():
    config = Config.from_args(...)
    assert config.path is not None
    assert config.use_regex or config.use_ner
```

Test validation:

```python
def test_path_validation():
    config = Config(...)
    is_valid, error = config.validate_path()
    assert is_valid or error is not None
```
