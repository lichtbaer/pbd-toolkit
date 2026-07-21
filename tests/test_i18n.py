"""Tests for CLI internationalization (core.i18n + LANGUAGE-driven CLI output)."""

import os

import pytest
from typer.testing import CliRunner

from core import i18n
from core.cli import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def _clean_language_env():
    """Ensure LANGUAGE doesn't leak between tests."""
    original = os.environ.get("LANGUAGE")
    yield
    if original is None:
        os.environ.pop("LANGUAGE", None)
    else:
        os.environ["LANGUAGE"] = original


class TestResolveLanguage:
    def test_explicit_de(self, monkeypatch):
        monkeypatch.setenv("LANGUAGE", "de")
        assert i18n.resolve_language() == "de"

    def test_explicit_en(self, monkeypatch):
        monkeypatch.setenv("LANGUAGE", "en")
        assert i18n.resolve_language() == "en"

    def test_unset_falls_back_to_english(self, monkeypatch):
        monkeypatch.delenv("LANGUAGE", raising=False)
        assert i18n.resolve_language() == "en"

    def test_unsupported_locale_falls_back_to_english(self, monkeypatch):
        monkeypatch.setenv("LANGUAGE", "fr")
        assert i18n.resolve_language() == "en"

    def test_empty_string_falls_back_to_english(self, monkeypatch):
        monkeypatch.setenv("LANGUAGE", "")
        assert i18n.resolve_language() == "en"


class TestGetTranslator:
    def test_german_translates_known_string(self):
        translate = i18n.get_translator("de")
        assert translate("Aborted.") == "Abgebrochen."

    def test_english_is_identity_for_known_string(self):
        translate = i18n.get_translator("en")
        assert translate("Aborted.") == "Aborted."

    def test_unknown_string_passes_through_untranslated(self):
        translate = i18n.get_translator("de")
        assert translate("Not in any catalog") == "Not in any catalog"


class TestCliLanguageSnapshots:
    """Snapshot a few CLI error paths under LANGUAGE=de / LANGUAGE=en."""

    def test_scan_missing_path_de(self, monkeypatch):
        monkeypatch.setenv("LANGUAGE", "de")
        result = runner.invoke(app, ["scan", "/does/not/exist"])
        assert "Scan-Pfad existiert nicht: /does/not/exist" in result.output

    def test_scan_missing_path_en(self, monkeypatch):
        monkeypatch.setenv("LANGUAGE", "en")
        result = runner.invoke(app, ["scan", "/does/not/exist"])
        assert "Scan path does not exist: /does/not/exist" in result.output

    def test_test_pattern_no_findings_de(self, monkeypatch):
        monkeypatch.setenv("LANGUAGE", "de")
        result = runner.invoke(app, ["test-pattern", "--text", "nothing to see here"])
        assert "Keine PII im angegebenen Text erkannt." in result.output

    def test_test_pattern_no_findings_en(self, monkeypatch):
        monkeypatch.setenv("LANGUAGE", "en")
        result = runner.invoke(app, ["test-pattern", "--text", "nothing to see here"])
        assert "No PII detected in the provided text." in result.output

    def test_query_missing_index_de(self, monkeypatch):
        monkeypatch.setenv("LANGUAGE", "de")
        result = runner.invoke(app, ["query", "/no/such/index", "some text"])
        assert "Index-Metadatendatei nicht gefunden" in result.output

    def test_query_missing_index_en(self, monkeypatch):
        monkeypatch.setenv("LANGUAGE", "en")
        result = runner.invoke(app, ["query", "/no/such/index", "some text"])
        assert "Index metadata file not found" in result.output
