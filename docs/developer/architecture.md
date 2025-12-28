# Architecture

This document provides an overview of the PII Toolkit's architecture and design principles.

## Overview

The PII Toolkit is a modular, extensible system for detecting personally identifiable information (PII) in various file formats.

## Core Components

### Main Entry Point

**Files**: `main.py`, `setup.py`

- **setup.py**: Handles CLI argument parsing, logging setup, output writer creation
- **main.py**: Main entry point that:
  - Uses setup functions for initialization
  - Creates ApplicationContext for dependency injection
  - Coordinates file scanning via FileScanner
  - Manages output generation via OutputWriter

### Core Modules

**Directory**: `core/`

- **scanner.py**: FileScanner class for directory traversal and file discovery
- **processor.py**: TextProcessor class for text extraction and PII detection
- **statistics.py**: Statistics class for tracking processing metrics
- **context.py**: ApplicationContext dataclass for dependency injection
- **config_loader.py**: ConfigLoader for loading YAML/JSON config files
- **exceptions.py**: Custom exception types
- **engines/**: Detection engine implementations and registry

### Configuration System

**Files**: `config.py`, `core/config_loader.py`

The `Config` class manages:
- Configuration from CLI arguments and config files (YAML/JSON)
- NER model loading (GLiNER, spaCy, Ollama, OpenAI)
- Regex pattern compilation
- Engine-specific settings
- Resource limits and timeouts

The `ConfigLoader` handles:
- Loading configuration from YAML or JSON files
- Merging config file values with CLI arguments (CLI takes precedence)

### File Processing

**Directory**: `file_processors/`

Modular file processor system:
- **Base Processor**: `base_processor.py` - Abstract base class
- **Registry**: `registry.py` - Automatic processor discovery
- **Processors**: Individual processors for each file format

### PII Detection

**Files**: `matches.py`, `core/processor.py`, `core/engines/`

The detection system consists of:
- **TextProcessor** (`core/processor.py`): Coordinates text extraction and PII detection
- **Engine Registry** (`core/engines/registry.py`): Manages multiple detection engines
- **Detection Engines**: RegexEngine, GLiNEREngine, SpacyNEREngine, PydanticAIEngine
- **PiiMatchContainer** (`matches.py`): Stores detected PII matches, handles whitelist filtering

**Note**: Output writing is handled by `core/writers.py`, not `matches.py`.

### Constants

**File**: `constants.py`

- Application-wide constants
- Output directory configuration
- NER model configuration

**Note**: The `globals.py` file exists but is no longer used. Global state has been eliminated through dependency injection and the ApplicationContext pattern.

## Design Patterns

### Processor Pattern

File processors follow a consistent interface:

```python
class BaseFileProcessor:
    def can_process(self, extension: str, file_path: str = "") -> bool:
        """Check if this processor can handle the file."""
        pass
    
    def extract_text(self, file_path: str) -> str:
        """Extract text content from the file."""
        pass
```

### Registry Pattern

The `FileProcessorRegistry` automatically discovers and manages processors:
- Processors register themselves on import
- Registry selects appropriate processor for each file
- Caching for performance optimization

### Strategy Pattern

Detection methods (regex vs. NER) are implemented as strategies:
- Both methods can be enabled simultaneously
- Easy to add new detection methods
- Independent configuration

## Data Flow

```
1. Command Line Arguments (setup.py)
   ↓
2. Configuration Setup (config.py, core/config_loader.py)
   ↓
3. Application Context Creation (core/context.py)
   ↓
4. File Discovery (core/scanner.py - FileScanner)
   ↓
5. Processor Selection (file_processors/registry.py)
   ↓
6. Text Extraction (file_processors/*.py)
   ↓
7. PII Detection (core/processor.py - TextProcessor)
   ↓
   - Engine Registry (core/engines/registry.py)
   - Multiple engines: regex, GLiNER, spaCy, Ollama, OpenAI
   ↓
8. Whitelist Filtering (matches.py - PiiMatchContainer)
   ↓
9. Output Generation (core/writers.py - OutputWriter)
   - CSV, JSON, or XLSX format
```

## Threading Model

The toolkit uses a callback-based approach for file processing:
- FileScanner walks the directory tree and calls a callback for each file
- Files are processed sequentially by default
- Each detection engine handles thread safety internally (locks for model calls)
- Match storage uses locks for thread safety

## Error Handling

Errors are collected during processing:
- File-level errors (permission, corruption, etc.)
- Processing errors (extraction failures)
- NER model errors (GPU, memory, etc.)

All errors are logged and reported in the output.

## Internationalization

The toolkit supports multiple languages:
- German (default)
- English

Translation files are in `locales/` directory using gettext.

## Extension Points

### Adding File Processors

See [Adding File Processors](adding-processors.md) for details.

### Adding Detection Methods

See [Engines Documentation](engines.md) for details on adding new detection engines.

For regex patterns:
1. Add pattern to `config_types.json`
2. Pattern is automatically compiled in `config.py`
3. RegexEngine automatically uses all patterns from config

### Adding Output Formats

1. Add format option to CLI arguments in `setup.py`
2. Implement output writer class in `core/writers.py` (inherit from OutputWriter)
3. Register in `core/writers.py` `create_output_writer()` function
4. No changes needed to `PiiMatchContainer` or `main.py`

## Performance Considerations

### Memory Management

- PDFs are processed in chunks
- Large files are handled efficiently
- Memory usage scales with number of matches

### Processing Speed

- Regex detection is very fast
- NER detection is slower (model inference)
- File I/O is optimized
- Progress tracking has minimal overhead

### Scalability

- Handles large directories (millions of files)
- Configurable file size limits
- Stop-count option for testing
- Progress reporting for long operations

## Testing

See [Testing](testing.md) for information on the test suite.

## Dependencies

Key dependencies:
- `gliner`: NER model
- `pdfminer.six`: PDF processing
- `python-docx`: DOCX processing
- `beautifulsoup4`: HTML processing
- `openpyxl`: Excel output
- `tqdm`: Progress bars

See `requirements.txt` for complete list.
