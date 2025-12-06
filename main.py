#!/usr/bin/env python3
"""PII Toolkit main entry point.

This module provides the main entry point for the PII Toolkit CLI.
It can be executed directly (with shebang) or as a module.

Usage:
    ./main.py --path /data --regex
    python main.py --path /data --regex
    python -m main --path /data --regex
    pii-toolkit --path /data --regex  # After installation
"""

import sys

# Import Typer CLI
from core.cli import cli

# Export cli function for entry point
__all__ = ["cli"]

if __name__ == "__main__":
    cli()
