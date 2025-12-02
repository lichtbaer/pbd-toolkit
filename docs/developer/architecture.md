# Architecture

This document provides an overview of the PII Toolkit's architecture and design principles.

## Overview

The PII Toolkit is a modular, extensible system for detecting personally identifiable information (PII) in various file formats.

## Core Components

### Main Entry Point

**File**: `main.py`

The main entry point that:
- Parses command-line arguments
- Initializes configuration
- Coordinates file scanning
- Manages output generation

### Configuration System

**File**: `config.py`

The `Config` class manages:
- Command-line argument parsing
- NER model loading
- Regex pattern compilation
- Logging setup
- Output file handling

### File Processing

**Directory**: `file_processors/`

Modular file processor system:
- **Base Processor**: `base_processor.py` - Abstract base class
- **Registry**: `registry.py` - Automatic processor discovery
- **Processors**: Individual processors for each file format

### PII Detection

**File**: `matches.py`

The `PiiMatchContainer` class:
- Stores detected PII matches
- Handles whitelist filtering
- Manages output writing (CSV, JSON, XLSX)

### Constants and Globals

**Files**: `constants.py`, `globals.py`

- Application-wide constants
- Global state management
- Internationalization setup

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
1. Command Line Arguments
   ↓
2. Configuration Setup (config.py)
   ↓
3. File Discovery (os.walk)
   ↓
4. Processor Selection (registry.py)
   ↓
5. Text Extraction (file_processors/*.py)
   ↓
6. PII Detection (regex/NER)
   ↓
7. Whitelist Filtering (matches.py)
   ↓
8. Output Generation (CSV/JSON/XLSX)
```

## Threading Model

The toolkit uses a single-threaded approach for file processing:
- Files are processed sequentially
- NER model calls are serialized (thread-safe)
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

1. Add pattern to `config_types.json`
2. Update regex compilation in `config.py`
3. Add processing logic in `main.py`

### Adding Output Formats

1. Add format option to CLI arguments
2. Implement output writer in `main.py`
3. Update `PiiMatchContainer` if needed

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
