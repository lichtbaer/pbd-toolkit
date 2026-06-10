"""Tests for the extraction-quality harness (eval/extraction.py)."""

import os
from pathlib import Path

import pytest

from eval.extraction import (
    extract_text,
    load_extraction_manifest,
    run_extraction_eval,
)

MANIFEST = (
    Path(__file__).resolve().parents[1]
    / "eval"
    / "datasets"
    / "extraction"
    / "manifest.json"
)


class TestExtractionManifest:
    def test_shipped_manifest_full_recall(self):
        """Every expected snippet in the shipped manifest must be extracted.

        Hermetic: the fixtures are plain-text formats (CSV, Markdown), so this runs
        offline with no optional binary dependencies.  A drop signals an extraction
        regression (e.g. CSV column-header context lost).
        """
        result = run_extraction_eval(MANIFEST)
        assert result.recall == 1.0, [
            (r.file, r.missing) for r in result.per_file if r.missing
        ]
        assert result.forbidden_hits == 0

    def test_manifest_loads_relative_paths(self):
        docs, base = load_extraction_manifest(MANIFEST)
        assert base.name == "extraction"
        assert any(d.file == "contacts.csv" for d in docs)

    def test_missing_manifest_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            run_extraction_eval(tmp_path / "nope.json")


class TestExtractionDocxTable:
    """A DOCX table cell (IBAN) must survive extraction — the historical gap."""

    def test_docx_table_cell_extracted(self, tmp_path):
        docx = pytest.importorskip("docx")
        path = os.path.join(tmp_path, "table.docx")
        document = docx.Document()
        document.add_paragraph("Stammdaten")
        table = document.add_table(rows=2, cols=2)
        table.cell(0, 0).text = "IBAN"
        table.cell(1, 0).text = "DE89 3704 0044 0532 0130 00"
        document.save(path)

        text = extract_text(path)
        assert "DE89 3704 0044 0532 0130 00" in text
