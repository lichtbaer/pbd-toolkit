"""Tests for the `doctor` CLI command."""

from typer.testing import CliRunner

from core.cli import app


def test_doctor_command_ok():
    runner = CliRunner()
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "Doctor:" in result.stdout


def test_doctor_command_json():
    runner = CliRunner()
    result = runner.invoke(app, ["doctor", "--json"])
    assert result.exit_code == 0
    assert '"ok":' in result.stdout

