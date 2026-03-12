#!/usr/bin/env python3
"""PII Toolkit main entry point.

This module provides the main entry point for the PII Toolkit CLI.
It can be executed directly (with shebang) or as a module.

Usage:
    ./main.py scan /data --regex
    python main.py scan /data --regex
    python -m main scan /data --regex
    pii-toolkit scan /data --regex  # After installation
"""

# Import Typer CLI
from core.cli import cli

# Export cli function for entry point
__all__ = ["cli"]

if __name__ == "__main__":
    cli()
