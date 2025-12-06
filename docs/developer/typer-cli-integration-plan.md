# Typer CLI Integration Plan

## Overview

This document outlines the plan for integrating Typer as the CLI library and making the tool usable as a proper command-line tool with shebang support and installation capabilities.

## Current State

### Current CLI Implementation
- Uses `argparse` for argument parsing (in `setup.py`)
- Entry point: `main.py` (executed as `python main.py`)
- No entry points defined in `setup.py`
- No shebang support
- Manual execution required: `python main.py --path ...`

### Current Structure
```
main.py              # Main entry point, imports setup
setup.py             # Contains argparse setup and configuration
core/                # Core functionality
```

## Goals

1. **Migrate from argparse to Typer**
   - Better type safety with type hints
   - Automatic help generation
   - Cleaner code structure
   - Better support for subcommands (future extensibility)

2. **Enable CLI Tool Installation**
   - Add entry points in `setup.py`
   - Allow installation as `pii-toolkit` or `pii-toolkit-scan` command
   - Support `pip install -e .` for development

3. **Add Shebang Support**
   - Add `#!/usr/bin/env python3` to main entry point
   - Make script executable
   - Allow direct execution: `./main.py --path ...`

4. **Maintain Backward Compatibility**
   - Keep existing argument structure
   - Preserve all current functionality
   - Maintain same exit codes

## Implementation Plan

### Phase 1: Create Typer CLI Module

**File: `core/cli.py`** (new file)

Create a new CLI module using Typer that:
- Defines all current CLI arguments using Typer's type hints
- Maintains the same argument names and behavior
- Integrates with existing setup functions
- Handles config file loading
- Provides proper error handling

**Key Features:**
- Use `typer.Typer()` for main app
- Use `typer.Option()` for optional arguments
- Use `typer.Argument()` for required arguments
- Support for callbacks for validation
- Integration with existing translation system

### Phase 2: Refactor main.py

**Changes to `main.py`:**
- Add shebang: `#!/usr/bin/env python3`
- Import and use Typer CLI from `core/cli.py`
- Keep existing business logic
- Maintain same structure for processing

**Shebang considerations:**
- Use `#!/usr/bin/env python3` for maximum compatibility
- Ensure script is executable (chmod +x)
- Handle both direct execution and module execution

### Phase 3: Update setup.py

**Changes to `setup.py`:**
- Add `typer` and `rich` to dependencies (Typer uses Rich for formatting)
- Add entry points for CLI commands:
  ```python
  entry_points={
      'console_scripts': [
          'pii-toolkit=main:cli',
          'pii-toolkit-scan=main:cli',  # Alternative name
      ],
  }
  ```
- Update version information
- Ensure proper package metadata

### Phase 4: Create CLI Wrapper Function

**File: `main.py` or `core/cli.py`:**

Create a wrapper function that:
- Initializes Typer app
- Defines the main scan command
- Handles all current arguments
- Calls existing setup and processing logic
- Maintains backward compatibility

**Structure:**
```python
import typer
from typing import Optional
from pathlib import Path

app = typer.Typer(
    name="pii-toolkit",
    help="Scan directories for personally identifiable information",
    add_completion=False
)

@app.command()
def scan(
    path: str = typer.Argument(..., help="Root directory to scan"),
    regex: bool = typer.Option(False, "--regex", help="Use regex detection"),
    ner: bool = typer.Option(False, "--ner", help="Use GLiNER NER"),
    # ... all other options
):
    """Main scan command."""
    # Call existing setup and processing logic
    pass
```

### Phase 5: Migration Strategy

**Backward Compatibility:**
1. Keep `setup.py` functions for internal use
2. Create adapter layer between Typer and existing setup
3. Maintain argparse compatibility during transition
4. Test both execution methods

**Migration Steps:**
1. Create `core/cli.py` with Typer implementation
2. Update `main.py` to use Typer while keeping old code commented
3. Test thoroughly
4. Remove argparse code after validation
5. Update documentation

## Technical Details

### Typer Advantages

1. **Type Safety:**
   - Automatic type validation
   - Better IDE support
   - Clearer function signatures

2. **Better Help:**
   - Automatic help generation
   - Rich formatting support
   - Better error messages

3. **Extensibility:**
   - Easy to add subcommands
   - Better structure for complex CLIs
   - Support for command groups

4. **Modern Python:**
   - Uses type hints
   - Follows modern Python practices
   - Better integration with tools

### Shebang Implementation

**File: `main.py`**
```python
#!/usr/bin/env python3
"""
PII Toolkit - Scan directories for personally identifiable information.
"""

import sys
# ... rest of imports
```

**Considerations:**
- Use `python3` explicitly (not `python`)
- `env` allows finding Python in PATH
- Script must be executable: `chmod +x main.py`
- Works on Unix/Linux/macOS
- Windows: Use `python main.py` (shebang ignored)

### Entry Points Configuration

**File: `setup.py`**
```python
from setuptools import setup

setup(
    # ... existing config
    entry_points={
        'console_scripts': [
            'pii-toolkit=main:cli',
        ],
    },
    install_requires=[
        # ... existing dependencies
        'typer>=0.9.0',
        'rich>=13.0.0',  # Used by Typer for formatting
    ],
)
```

**Usage after installation:**
```bash
# Install in development mode
pip install -e .

# Use as CLI tool
pii-toolkit --path /data --regex --ner

# Or with alternative name
pii-toolkit-scan --path /data --regex
```

### CLI Function Structure

**File: `core/cli.py`**
```python
"""CLI interface using Typer."""

import typer
from typing import Optional
from pathlib import Path
import sys

from setup import setup, create_config
from core.context import ApplicationContext
# ... other imports

app = typer.Typer(
    name="pii-toolkit",
    help="Scan directories for personally identifiable information",
    add_completion=False,
    no_args_is_help=True
)

@app.command()
def scan(
    # Required arguments
    path: str = typer.Argument(..., help="Root directory to scan recursively"),
    
    # Detection methods
    regex: bool = typer.Option(False, "--regex", help="Use regular expressions"),
    ner: bool = typer.Option(False, "--ner", help="Use GLiNER NER"),
    spacy_ner: bool = typer.Option(False, "--spacy-ner", help="Use spaCy NER"),
    # ... all other options
    
    # Output options
    verbose: bool = typer.Option(False, "-v", "--verbose", help="Verbose output"),
    quiet: bool = typer.Option(False, "-q", "--quiet", help="Quiet mode"),
    
    # Config file
    config: Optional[Path] = typer.Option(None, "--config", help="Config file path"),
) -> None:
    """Scan directory for PII using specified detection methods."""
    # Implementation that calls existing setup and processing logic
    pass

def cli() -> None:
    """Entry point for CLI."""
    app()
```

**File: `main.py`**
```python
#!/usr/bin/env python3
"""PII Toolkit main entry point."""

import sys
from core.cli import cli

if __name__ == "__main__":
    cli()
```

## Testing Strategy

### Test Cases

1. **Direct Execution:**
   ```bash
   ./main.py --path /data --regex
   ```

2. **Module Execution:**
   ```bash
   python -m main --path /data --regex
   ```

3. **Installed Command:**
   ```bash
   pip install -e .
   pii-toolkit --path /data --regex
   ```

4. **Backward Compatibility:**
   - All existing arguments work
   - Same exit codes
   - Same output formats
   - Config file support

### Validation

- [ ] All current CLI arguments work
- [ ] Help output is correct
- [ ] Config file loading works
- [ ] Exit codes are preserved
- [ ] Output formats unchanged
- [ ] Translation system works
- [ ] Logging works correctly
- [ ] Error handling works

## Additional CLI Tool Features

### 1. Shell Completion

Typer supports automatic shell completion:
- Bash completion
- Zsh completion
- Fish completion

**Implementation:**
```python
app = typer.Typer(add_completion=True)
```

**Usage:**
```bash
# Enable completion
pii-toolkit --install-completion bash
```

### 2. Version Command

Typer can automatically add version:
```python
app = typer.Typer(
    # ...
    version="1.0.0"
)
```

### 3. Rich Output (Optional)

Typer uses Rich for better output:
- Colored help text
- Better error messages
- Progress bars (already using tqdm)
- Tables for structured output

### 4. Subcommands (Future)

Structure for future extensibility:
```python
app = typer.Typer()

@app.command()
def scan(...):
    """Scan command."""
    pass

@app.command()
def validate(...):
    """Validate config (future)."""
    pass

@app.command()
def export(...):
    """Export results (future)."""
    pass
```

## File Structure After Migration

```
.
├── main.py                 # Entry point with shebang, calls core.cli
├── setup.py                # Updated with entry points and typer dependency
├── core/
│   ├── cli.py             # NEW: Typer CLI implementation
│   ├── context.py         # Existing
│   ├── scanner.py         # Existing
│   └── ...                # Other existing modules
└── docs/
    └── developer/
        └── typer-cli-integration-plan.md  # This document
```

## Dependencies

### New Dependencies
- `typer>=0.9.0` - CLI framework
- `rich>=13.0.0` - Used by Typer for formatting (optional but recommended)

### No Breaking Changes
- All existing dependencies remain
- Optional: Rich can enhance output but not required

## Migration Checklist

- [ ] Create `core/cli.py` with Typer implementation
- [ ] Add shebang to `main.py`
- [ ] Update `setup.py` with entry points
- [ ] Add typer and rich to requirements
- [ ] Test direct execution (`./main.py`)
- [ ] Test module execution (`python -m main`)
- [ ] Test installed command (`pii-toolkit`)
- [ ] Update documentation
- [ ] Update README with installation instructions
- [ ] Test on different platforms (Linux, macOS, Windows)
- [ ] Remove argparse code (after validation)
- [ ] Update CI/CD if applicable

## Documentation Updates

### Files to Update

1. **README.md:**
   - Add installation instructions
   - Show new CLI usage
   - Document entry point name

2. **docs/user-guide/cli.md:**
   - Update examples to show new command name
   - Keep backward compatibility examples
   - Document installation

3. **docs/getting-started/installation.md:**
   - Add CLI installation instructions
   - Document entry points
   - Show development installation

## Rollback Plan

If issues arise:
1. Keep argparse code in separate branch
2. Maintain both implementations during transition
3. Use feature flag if needed
4. Can revert to argparse if necessary

## Timeline Estimate

- **Phase 1-2:** 2-3 hours (Typer implementation)
- **Phase 3:** 1 hour (setup.py updates)
- **Phase 4:** 1-2 hours (integration and testing)
- **Phase 5:** 2-3 hours (testing and validation)
- **Documentation:** 1 hour

**Total:** ~8-10 hours

## Success Criteria

1. ✅ Tool can be installed as CLI command
2. ✅ Tool can be executed with shebang
3. ✅ All existing functionality preserved
4. ✅ Better type safety and help output
5. ✅ Backward compatible
6. ✅ Documentation updated
7. ✅ Tests pass

## Notes

- Typer is built on Click but uses type hints
- Rich is optional but recommended for better UX
- Shebang works on Unix/Linux/macOS, ignored on Windows
- Entry points work on all platforms
- Can maintain both argparse and Typer during transition
