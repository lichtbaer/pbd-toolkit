"""Tests for CLI commands using Typer CliRunner."""

from pathlib import Path

import pytest

from typer.testing import CliRunner

from core.cli import app

runner = CliRunner()


class TestCliVersion:
    """Tests for --version option."""

    def test_version_option(self):
        """Test --version prints version and exits."""
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "pii-toolkit" in result.output

    def test_version_short_flag(self):
        """Test -V prints version."""
        result = runner.invoke(app, ["-V"])
        assert result.exit_code == 0
        assert "pii-toolkit" in result.output


class TestCliScan:
    """Tests for scan command."""

    def test_scan_help(self):
        """Test scan --help shows usage."""
        result = runner.invoke(app, ["scan", "--help"])
        assert result.exit_code == 0
        assert "scan" in result.output.lower()
        assert "path" in result.output.lower() or "directory" in result.output.lower()

    def test_scan_with_path_and_regex(self, temp_dir):
        """Test scan command with path and regex."""
        (Path(temp_dir) / "test.txt").write_text("Contact: user@example.com")
        result = runner.invoke(
            app,
            ["scan", temp_dir, "--regex", "--quiet"],
            catch_exceptions=False,
        )
        assert result.exit_code == 0

    def test_scan_invalid_path(self):
        """Test scan with invalid path fails."""
        result = runner.invoke(
            app,
            ["scan", "/nonexistent/path/12345", "--regex", "--quiet"],
            catch_exceptions=False,
        )
        assert result.exit_code != 0


class TestCliDoctor:
    """Tests for doctor command."""

    def test_doctor_help(self):
        """Test doctor --help shows usage."""
        result = runner.invoke(app, ["doctor", "--help"])
        assert result.exit_code == 0
        assert "doctor" in result.output.lower()

    def test_doctor_run(self):
        """Test doctor command runs."""
        result = runner.invoke(app, ["doctor"], catch_exceptions=False)
        assert result.exit_code in (0, 1)
