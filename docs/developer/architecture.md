# Architecture

This document provides an overview of the pbD Toolkit's architecture and design principles.

## Overview

The pbD Toolkit is a modular, extensible system for detecting personally identifiable information (PII) in various file formats.

## Core Components

### Main Entry Point

**Files**: `core/cli.py`, `core/cli_setup.py`, `core/scan_runner.py`

- **core/cli.py**: Typer-based CLI. Installed as the `pbd-toolkit` console script (also runnable as `python -m core.cli`). Implements the `scan` command, parses arguments, and delegates orchestration to `ScanRunner`.
- **core/cli_setup.py**: Shared setup helpers (i18n, logger setup, Config construction).
- **core/scan_runner.py**: `ScanRunner` application service — owns the shared scan pipeline (scanner/processor/writer orchestration, cache handling, reporting) used by both the CLI and the REST API.

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

**Scoped sub-configs.** `Config` groups related fields into four typed,
immutable-in-spirit sub-configs so individual components can depend on only
the settings they actually need instead of the entire object:

- `config.scan` (`ScanConfig`) — file discovery and safety limits (path,
  excludes, size/time caps, magic detection). Owns `validate_path()` /
  `validate_file_path()`.
- `config.engine` (`EngineConfig`) — detection engine selection and tuning
  (models, API URLs, thresholds).
- `config.output` (`OutputConfig`) — result formatting and streaming
  (output path, deduplication, chunking, analytics).
- `config.runtime` (`RuntimeConfig`) — cross-cutting runtime services:
  logger, verbosity, CSV sink.

Every sub-config field also exists as a top-level `Config` attribute for
backward compatibility (e.g. `config.verbose` and `config.runtime.verbose`
are the same value). `Config.__setattr__` keeps the sub-config **live**
in sync with the top-level mirror on every assignment — at construction
time and afterwards (e.g. CLI/config-file post-processing that does
`setattr(cfg, key, value)` in a loop). This only flows top-level ->
sub-config; mutating a sub-config object directly does not update the
top-level mirror.

`FileScanner` (`core/scanner.py`) is the first component migrated to depend
only on `config.scan` and `config.runtime` rather than the full `Config` —
new low-level components should follow the same pattern rather than reading
arbitrary top-level `Config` attributes. Engine and output/writer code still
receive the full `Config` object; narrowing those is tracked as follow-up
work (see issue #77).

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

The `EngineRegistry` follows the same pattern for detection engines.

**Registration lifecycle**: both registries hold process-wide, class-level state
populated exactly once, at import time — `file_processors/__init__.py` and
`core/engines/__init__.py` respectively call `register()` at module scope before
any worker thread or request handler runs. Application code (CLI, API, scanner
workers) never registers anything itself; it only reads the registry through
`get_processor`/`get_engine` and friends.

**Thread safety**: `register()` is not thread-safe and must only be called during
import or from a single-threaded setup/test context. Reads are safe to call
concurrently once import-time registration has finished — CPython's GIL makes
individual dict/list reads atomic, and the tables are not mutated during a scan.

**Isolation for tests and API/server use**: because the registries are shared,
process-wide state, calling `register()` or `clear()` directly in a test leaks
into every test that runs afterwards in the same process. Both registries expose:
- `isolated()` — a context manager that scopes `register()`/`clear()` calls to a
  `with` block and restores the previous table on exit, even if the block raises.
  Use this in tests instead of calling `register()`/`clear()` directly.
- `snapshot()` — returns an independent, read-only view (`EngineRegistrySnapshot` /
  `FileProcessorRegistrySnapshot`) of what was registered at that moment, unaffected
  by later `register()` calls against the global registry. Useful for a long-lived
  API/server process that wants a stable engine/processor set for a request.

### Strategy Pattern

Detection methods (regex vs. NER) are implemented as strategies:
- Both methods can be enabled simultaneously
- Easy to add new detection methods
- Independent configuration

## Data Flow

```
1. Command Line Arguments (core/cli.py)
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

The toolkit uses a callback-based approach for file processing, with concurrency
ownership centralized in one place (issue #79):

- `ScanRunner` (`core/scan_runner.py`) is the **sole owner** of the file-worker
  thread pool: it decides whether to create a `ThreadPoolExecutor` from the
  resolved `worker_count` (`--mode safe` → 1, i.e. no executor at all; `--jobs`
  or `--mode fast`/`balanced` → a real pool), submits work to it via the
  `file_callback` it hands to `FileScanner.scan`, and shuts it down in a
  `finally` block so cleanup happens even if scanning raises.
- `FileScanner` itself never constructs an executor. It stays sequential
  internally and only knows about `concurrent.futures.Future` in the abstract:
  if a callback returns one, the scanner tracks it in `pending_futures` and
  bounds that list (`max_pending_futures`) to avoid unbounded memory growth on
  very large directory trees, draining/awaiting futures and surfacing their
  exceptions as scan errors.
- The REST API (`api/scanner_service.py`) forces `worker_count=1`, so API scans
  always take the sequential path through the same `ScanRunner`.
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

1. Add format option to CLI arguments in `core/cli.py`
2. Implement output writer class in `core/writers.py` (inherit from OutputWriter)
3. Register in `core/writers.py` `create_output_writer()` function
4. No changes needed to `PiiMatchContainer` or `core/cli.py`

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
- Per-engine concurrency limits to avoid overwhelming local model servers (e.g. vLLM/LocalAI/Ollama)

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
