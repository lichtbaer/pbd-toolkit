"""Pytest configuration and shared fixtures."""

import os
import tempfile
import pytest
from pathlib import Path


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def sample_text_file(temp_dir):
    """Create a sample text file for testing."""
    file_path = os.path.join(temp_dir, "test.txt")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("This is a test file with email test@example.com and IBAN DE89 3704 0044 0532 0130 00.")
    return file_path


@pytest.fixture
def sample_html_file(temp_dir):
    """Create a sample HTML file for testing."""
    file_path = os.path.join(temp_dir, "test.html")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("""
        <html>
        <body>
            <p>Contact: user@example.com</p>
            <p>IBAN: DE89 3704 0044 0532 0130 00</p>
        </body>
        </html>
        """)
    return file_path


@pytest.fixture
def empty_whitelist():
    """Return an empty whitelist."""
    return []


@pytest.fixture
def sample_whitelist():
    """Return a sample whitelist."""
    return ["test@example.com", "info@"]
