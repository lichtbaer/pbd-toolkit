"""Unit tests for ``core.writers``.

Complements ``tests/test_output_writers_streaming.py`` (which covers the happy
path of CSV/JSON/JSONL/XLSX/statistics and the CSV open failure). This file
focuses on: header on/off, unicode round-trips, empty outputs, optional context
fields, every ``OutputError`` path, the streaming JSON writer, the HTML and SARIF
writers, and the factory's silent CSV fallback for unknown formats.
"""

from __future__ import annotations

import csv
import json
import sys

import pytest

from core.exceptions import OutputError
from core.matches import PiiMatch
from core.writers import (
    CsvWriter,
    HtmlWriter,
    JsonlWriter,
    JsonWriter,
    OutputWriter,
    PrivacyStatisticsWriter,
    SarifWriter,
    StreamingJsonWriter,
    XlsxWriter,
    create_output_writer,
)

UNICODE_TEXT = "Müller Straße 12 – 😀"


def _match(**overrides) -> PiiMatch:
    base = dict(
        text="test@example.com",
        file="/data/a.txt",
        type="REGEX_EMAIL",
        ner_score=None,
        engine="regex",
        metadata={},
        severity="MEDIUM",
    )
    base.update(overrides)
    return PiiMatch(**base)


@pytest.fixture
def bad_path(tmp_path):
    """A path inside a directory that does not exist (open() raises OSError)."""
    return str(tmp_path / "missing-dir" / "out.file")


# ---------------------------------------------------------------------------
# CsvWriter
# ---------------------------------------------------------------------------


class TestCsvWriter:
    def test_rows_and_header(self, tmp_path):
        out = tmp_path / "f.csv"
        w = CsvWriter(str(out))
        w.write_match(_match(ner_score=0.75))
        w.write_match(_match(text="second", type="NER_PERSON", engine="gliner"))
        w.finalize()

        with open(out, newline="", encoding="utf-8") as fh:
            rows = list(csv.reader(fh))
        assert rows[0] == ["Match", "File", "Type", "Score", "Engine", "Severity"]
        assert rows[1] == [
            "test@example.com",
            "/data/a.txt",
            "REGEX_EMAIL",
            "0.75",
            "regex",
            "MEDIUM",
        ]
        assert rows[2][:3] == ["second", "/data/a.txt", "NER_PERSON"]
        assert rows[2][3] == ""  # None score serialises as empty cell
        assert len(rows) == 3

    def test_header_can_be_disabled(self, tmp_path):
        out = tmp_path / "f.csv"
        w = CsvWriter(str(out), include_header=False)
        w.write_match(_match())
        w.finalize()

        with open(out, newline="", encoding="utf-8") as fh:
            rows = list(csv.reader(fh))
        assert rows == [
            ["test@example.com", "/data/a.txt", "REGEX_EMAIL", "", "regex", "MEDIUM"]
        ]

    def test_empty_output_without_header_is_empty_file(self, tmp_path):
        out = tmp_path / "f.csv"
        CsvWriter(str(out), include_header=False).finalize()
        assert out.read_bytes() == b""

    def test_empty_output_with_header_only(self, tmp_path):
        out = tmp_path / "f.csv"
        CsvWriter(str(out)).finalize()
        assert out.read_text(encoding="utf-8").strip() == (
            "Match,File,Type,Score,Engine,Severity"
        )

    def test_unicode_round_trip(self, tmp_path):
        out = tmp_path / "f.csv"
        w = CsvWriter(str(out))
        w.write_match(_match(text=UNICODE_TEXT, file="/pfad/ärger.txt"))
        w.finalize()

        with open(out, newline="", encoding="utf-8") as fh:
            rows = list(csv.reader(fh))
        assert rows[1][0] == UNICODE_TEXT
        assert rows[1][1] == "/pfad/ärger.txt"

    def test_handles_and_idempotent_finalize(self, tmp_path):
        out = tmp_path / "f.csv"
        w = CsvWriter(str(out))

        assert w.supports_streaming is True
        assert w.file_handle is not None and not w.file_handle.closed
        assert hasattr(w.get_writer(), "writerow")

        w.finalize()
        assert w.file_handle is None
        w.finalize()  # second call must be a no-op, not an error

    def test_metadata_is_ignored(self, tmp_path):
        out = tmp_path / "f.csv"
        w = CsvWriter(str(out))
        w.finalize(metadata={"ignored": True})
        assert "ignored" not in out.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# JsonWriter
# ---------------------------------------------------------------------------


class TestJsonWriter:
    def test_optional_fields_only_when_present(self, tmp_path):
        out = tmp_path / "f.json"
        w = JsonWriter(str(out))
        w.write_match(_match(metadata={"k": [1, 2]}))
        w.write_match(
            _match(text="ctx", context_before="<<", context_after=">>", char_offset=7)
        )
        w.finalize()

        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["metadata"] == {}
        first, second = data["findings"]
        assert first == {
            "text": "test@example.com",
            "file": "/data/a.txt",
            "type": "REGEX_EMAIL",
            "score": None,
            "engine": "regex",
            "severity": "MEDIUM",
            "metadata": {"k": [1, 2]},
        }
        assert second["context_before"] == "<<"
        assert second["context_after"] == ">>"
        assert second["char_offset"] == 7

    def test_unicode_is_not_escaped(self, tmp_path):
        out = tmp_path / "f.json"
        w = JsonWriter(str(out))
        w.write_match(_match(text=UNICODE_TEXT))
        w.finalize(metadata={"scan": "Prüfung"})

        raw = out.read_text(encoding="utf-8")
        assert UNICODE_TEXT in raw
        assert "Prüfung" in raw
        assert "\\u" not in raw

    def test_open_failure_raises_output_error(self, bad_path):
        with pytest.raises(OutputError, match="Failed to open output file"):
            JsonWriter(bad_path)

    def test_finalize_failure_raises_and_cleans_body(self, tmp_path):
        out = tmp_path / "f.json"
        w = JsonWriter(str(out))
        w.write_match(_match())
        body = str(out) + ".findings.tmp"
        w.file_path = str(tmp_path / "missing" / "f.json")  # unwritable target

        with pytest.raises(OutputError, match="Failed to write JSON output"):
            w.finalize()

        # The temporary body file is always cleaned up, even on failure.
        assert not (tmp_path / "f.json.findings.tmp").exists()
        assert not (tmp_path / "f.json").exists()
        assert body.endswith(".findings.tmp")

    def test_header_flag_accepted(self, tmp_path):
        out = tmp_path / "f.json"
        w = JsonWriter(str(out), include_header=False)
        assert w.include_header is False
        w.finalize()
        assert json.loads(out.read_text(encoding="utf-8")) == {
            "metadata": {},
            "findings": [],
        }


# ---------------------------------------------------------------------------
# StreamingJsonWriter
# ---------------------------------------------------------------------------


class TestStreamingJsonWriter:
    def test_opening_is_written_immediately(self, tmp_path):
        out = tmp_path / "s.json"
        w = StreamingJsonWriter(str(out))
        w.file_handle.flush()

        assert out.read_text(encoding="utf-8") == '{"metadata": null, "findings": [\n'
        assert w.supports_streaming is True
        w.finalize()

    def test_metadata_patched_and_findings_ordered(self, tmp_path):
        out = tmp_path / "s.json"
        w = StreamingJsonWriter(str(out))
        w.write_match(_match(text="one"))
        w.write_match(_match(text="two", ner_score=0.5, char_offset=3))
        w.finalize(metadata={"scan_id": "abc", "n": 2})

        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["metadata"] == {"scan_id": "abc", "n": 2}
        assert [f["text"] for f in data["findings"]] == ["one", "two"]
        assert data["findings"][1]["char_offset"] == 3
        assert "char_offset" not in data["findings"][0]

    def test_no_metadata_leaves_json_null(self, tmp_path):
        """Without metadata the placeholder stays ``null`` (unlike JsonWriter's ``{}``)."""
        out = tmp_path / "s.json"
        w = StreamingJsonWriter(str(out))
        w.write_match(_match())
        w.finalize()

        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["metadata"] is None
        assert len(data["findings"]) == 1

    def test_empty_metadata_dict_is_treated_as_no_metadata(self, tmp_path):
        out = tmp_path / "s.json"
        w = StreamingJsonWriter(str(out))
        w.finalize(metadata={})

        assert json.loads(out.read_text(encoding="utf-8")) == {
            "metadata": None,
            "findings": [],
        }

    def test_empty_findings_with_metadata(self, tmp_path):
        out = tmp_path / "s.json"
        w = StreamingJsonWriter(str(out))
        w.finalize(metadata={"a": 1})

        assert json.loads(out.read_text(encoding="utf-8")) == {
            "metadata": {"a": 1},
            "findings": [],
        }

    def test_only_first_placeholder_is_patched(self, tmp_path):
        """A finding whose text contains the placeholder literal is left untouched."""
        out = tmp_path / "s.json"
        w = StreamingJsonWriter(str(out))
        w.write_match(_match(text='"metadata": null'))
        w.finalize(metadata={"x": 1})

        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["metadata"] == {"x": 1}
        assert data["findings"][0]["text"] == '"metadata": null'

    def test_unicode(self, tmp_path):
        out = tmp_path / "s.json"
        w = StreamingJsonWriter(str(out))
        w.write_match(_match(text=UNICODE_TEXT))
        w.finalize(metadata={"ort": "Köln"})

        raw = out.read_text(encoding="utf-8")
        assert UNICODE_TEXT in raw and "Köln" in raw

    def test_open_failure_raises_output_error(self, bad_path):
        with pytest.raises(OutputError, match="Failed to open output file"):
            StreamingJsonWriter(bad_path)

    def test_finalize_failure_raises_output_error(self, tmp_path):
        out = tmp_path / "s.json"
        w = StreamingJsonWriter(str(out))
        w.file_handle.close()  # writing to a closed handle raises ValueError...
        # ...which is not an OSError, so it propagates unchanged: document that.
        with pytest.raises(ValueError):
            w.finalize()

    def test_finalize_rewrite_failure_raises_output_error(self, tmp_path):
        out = tmp_path / "s.json"
        w = StreamingJsonWriter(str(out))
        w.write_match(_match())
        # Redirect the metadata patch step to an unwritable location.
        w.file_path = str(tmp_path / "missing" / "s.json")

        with pytest.raises(OutputError, match="Failed to write streaming JSON output"):
            w.finalize(metadata={"a": 1})


# ---------------------------------------------------------------------------
# JsonlWriter
# ---------------------------------------------------------------------------


class TestJsonlWriter:
    def test_no_metadata_line_when_metadata_absent(self, tmp_path):
        out = tmp_path / "f.jsonl"
        w = JsonlWriter(str(out))
        w.write_match(_match())
        w.write_match(
            _match(text="b", context_before="x", context_after="y", char_offset=1)
        )
        w.finalize()

        lines = out.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 2
        assert "_metadata" not in lines[-1]
        second = json.loads(lines[1])
        assert (
            second["context_before"],
            second["context_after"],
            second["char_offset"],
        ) == (
            "x",
            "y",
            1,
        )
        assert "context_before" not in json.loads(lines[0])

    def test_empty_metadata_dict_writes_no_trailer(self, tmp_path):
        out = tmp_path / "f.jsonl"
        JsonlWriter(str(out)).finalize(metadata={})
        assert out.read_text(encoding="utf-8") == ""

    def test_empty_output_with_metadata_only(self, tmp_path):
        out = tmp_path / "f.jsonl"
        JsonlWriter(str(out)).finalize(metadata={"k": 1})
        assert json.loads(out.read_text(encoding="utf-8")) == {"_metadata": {"k": 1}}

    def test_unicode(self, tmp_path):
        out = tmp_path / "f.jsonl"
        w = JsonlWriter(str(out))
        w.write_match(_match(text=UNICODE_TEXT))
        w.finalize()
        raw = out.read_text(encoding="utf-8")
        assert UNICODE_TEXT in raw and "\\u" not in raw

    def test_handles_and_idempotent_finalize(self, tmp_path):
        out = tmp_path / "f.jsonl"
        w = JsonlWriter(str(out), include_header=False)
        assert w.supports_streaming is True
        assert w.file_handle is not None
        w.finalize(metadata={"a": 1})
        assert w.file_handle is None
        w.finalize(metadata={"a": 2})  # closed: must not write or raise
        assert out.read_text(encoding="utf-8").count("_metadata") == 1

    def test_open_failure_raises_output_error(self, bad_path):
        with pytest.raises(OutputError, match="Failed to open output file"):
            JsonlWriter(bad_path)


# ---------------------------------------------------------------------------
# XlsxWriter
# ---------------------------------------------------------------------------


def _load_rows(path, sheet):
    import openpyxl

    wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
    try:
        return wb.sheetnames, list(wb[sheet].iter_rows(values_only=True))
    finally:
        wb.close()


class TestXlsxWriter:
    def test_header_disabled(self, tmp_path):
        out = tmp_path / "f.xlsx"
        w = XlsxWriter(str(out), include_header=False)
        w.write_match(_match(ner_score=0.9))
        w.finalize()

        names, rows = _load_rows(out, "Findings")
        assert rows == [
            ("test@example.com", "/data/a.txt", "REGEX_EMAIL", 0.9, "regex", "MEDIUM")
        ]
        assert "Metadata" not in names

    def test_metadata_sheet_flattens_nested_values(self, tmp_path):
        out = tmp_path / "f.xlsx"
        w = XlsxWriter(str(out))
        w.finalize(
            metadata={
                "scan_id": "abc",
                "engines": ["regex", "gliner"],
                "stats": {"n": 1},
            }
        )

        names, rows = _load_rows(out, "Metadata")
        assert names == ["Findings", "Metadata"]
        assert rows[0] == ("Key", "Value")
        assert rows[1] == ("scan_id", "abc")
        assert json.loads(rows[2][1]) == ["regex", "gliner"]
        assert json.loads(rows[3][1]) == {"n": 1}

    def test_empty_output_has_header_only(self, tmp_path):
        out = tmp_path / "f.xlsx"
        XlsxWriter(str(out)).finalize()
        _, rows = _load_rows(out, "Findings")
        assert rows == [("Match", "File", "Type", "Score", "Engine", "Severity")]

    def test_unicode_cell(self, tmp_path):
        out = tmp_path / "f.xlsx"
        w = XlsxWriter(str(out))
        w.write_match(_match(text=UNICODE_TEXT))
        w.finalize()
        _, rows = _load_rows(out, "Findings")
        assert rows[1][0] == UNICODE_TEXT

    def test_missing_openpyxl_raises_output_error(self, tmp_path, monkeypatch):
        monkeypatch.setitem(sys.modules, "openpyxl", None)
        with pytest.raises(OutputError, match="openpyxl is required"):
            XlsxWriter(str(tmp_path / "f.xlsx"))

    def test_save_failure_raises_output_error(self, bad_path):
        # include_header=False keeps openpyxl's lazy sheet writer un-started, so the
        # never-saved workbook does not leak a half-open lxml generator at GC time.
        w = XlsxWriter(bad_path, include_header=False)  # only save() touches disk
        with pytest.raises(OutputError, match="Failed to save Excel file"):
            w.finalize()

    def test_supports_streaming(self, tmp_path):
        w = XlsxWriter(str(tmp_path / "f.xlsx"))
        assert w.supports_streaming is True
        w.finalize()


# ---------------------------------------------------------------------------
# PrivacyStatisticsWriter
# ---------------------------------------------------------------------------


class TestPrivacyStatisticsWriter:
    def test_no_metadata_writes_empty_sections(self, tmp_path):
        out = tmp_path / "stats.json"
        w = PrivacyStatisticsWriter(str(out))
        w.write_match(_match())
        w.write_match(_match())
        w.finalize()

        data = json.loads(out.read_text(encoding="utf-8"))
        assert data == {
            "metadata": {},
            "statistics_by_dimension": {},
            "statistics_by_module": {},
            "statistics_by_file_type": {},
            "summary": {},
            "performance_metrics": {},
        }
        # Individual findings are never persisted by this writer.
        assert "test@example.com" not in out.read_text(encoding="utf-8")
        assert w.supports_streaming is False

    def test_all_sections_are_passed_through(self, tmp_path):
        out = tmp_path / "stats.json"
        w = PrivacyStatisticsWriter(str(out))
        w.finalize(
            metadata={
                "statistics": {
                    "statistics_by_dimension": {"financial": 2},
                    "statistics_by_module": {"regex": 2},
                    "statistics_by_file_type": {".txt": 1},
                    "summary": {"total": 2},
                },
                "scan_metadata": {"path": "/pfad/ü"},
                "performance_metrics": {"duration_s": 0.1},
            }
        )

        raw = out.read_text(encoding="utf-8")
        data = json.loads(raw)
        assert data["statistics_by_module"] == {"regex": 2}
        assert data["statistics_by_file_type"] == {".txt": 1}
        assert data["performance_metrics"] == {"duration_s": 0.1}
        assert data["metadata"] == {"path": "/pfad/ü"}
        assert "\\u" not in raw

    def test_write_failure_raises_output_error(self, bad_path):
        with pytest.raises(OutputError, match="Failed to write statistics JSON output"):
            PrivacyStatisticsWriter(bad_path).finalize()


# ---------------------------------------------------------------------------
# HtmlWriter
# ---------------------------------------------------------------------------


class TestHtmlWriter:
    def test_report_contents_and_escaping(self, tmp_path):
        out = tmp_path / "r.html"
        w = HtmlWriter(str(out))
        w.write_match(_match(text="<script>alert(1)</script>", severity="CRITICAL"))
        w.write_match(_match(text="a", severity="HIGH", ner_score=0.42))
        w.write_match(_match(text="b", severity="HIGH"))
        w.write_match(_match(text="c", severity="BOGUS"))  # unknown: not counted
        w.write_match(_match(text="d", severity=None))
        w.finalize(
            metadata={"start_time": "2026-01-01", "duration": "1s", "files_scanned": 3}
        )

        page = out.read_text(encoding="utf-8")
        assert "<script>alert(1)</script>" not in page
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page
        assert '<div class="count">1</div><div class="label">CRITICAL</div>' in page
        assert '<div class="count">2</div><div class="label">HIGH</div>' in page
        assert '<div class="count">0</div><div class="label">MEDIUM</div>' in page
        assert '<div class="count">0</div><div class="label">LOW</div>' in page
        assert "Total findings: 5" in page
        assert "Start: 2026-01-01" in page
        assert "Files scanned: 3" in page
        assert page.count("<tr>") == 1 + 5  # header row + one per finding
        assert "<td>0.42</td>" in page
        assert w.supports_streaming is False

    def test_empty_report_uses_na_defaults(self, tmp_path):
        out = tmp_path / "r.html"
        HtmlWriter(str(out)).finalize()

        page = out.read_text(encoding="utf-8")
        assert "Start: N/A" in page
        assert "Duration: N/A" in page
        assert "Total findings: 0" in page
        assert '<tbody id="tbody">\n</tbody>' in page

    def test_metadata_values_are_escaped(self, tmp_path):
        out = tmp_path / "r.html"
        HtmlWriter(str(out)).finalize(metadata={"start_time": "<b>x</b>"})
        page = out.read_text(encoding="utf-8")
        assert "Start: &lt;b&gt;x&lt;/b&gt;" in page

    def test_write_failure_raises_output_error(self, bad_path):
        with pytest.raises(OutputError, match="Failed to write HTML output"):
            HtmlWriter(bad_path).finalize()


# ---------------------------------------------------------------------------
# SarifWriter
# ---------------------------------------------------------------------------


class TestSarifWriter:
    def test_rules_results_and_levels(self, tmp_path):
        out = tmp_path / "r.sarif"
        w = SarifWriter(str(out))
        w.write_match(_match(type="REGEX_IBAN", severity="CRITICAL", text="x" * 150))
        w.write_match(_match(type="REGEX_EMAIL", severity="MEDIUM"))
        w.write_match(_match(type="REGEX_IBAN", severity="HIGH", file="/b.txt"))
        w.write_match(_match(type="NER_PERSON", severity="LOW"))
        w.write_match(_match(type="X", severity="WEIRD"))
        w.write_match(_match(type="Y", severity=None, text=""))
        w.finalize()

        sarif = json.loads(out.read_text(encoding="utf-8"))
        assert sarif["version"] == "2.1.0"
        run = sarif["runs"][0]
        assert run["tool"]["driver"]["name"] == "pbd-toolkit"
        assert [r["id"] for r in run["tool"]["driver"]["rules"]] == [
            "REGEX_IBAN",
            "REGEX_EMAIL",
            "NER_PERSON",
            "X",
            "Y",
        ]
        results = run["results"]
        assert [r["level"] for r in results] == [
            "error",
            "warning",
            "error",
            "note",
            "note",
            "note",
        ]
        assert [r["ruleIndex"] for r in results] == [0, 1, 0, 2, 3, 4]
        assert len(results[0]["message"]["text"]) == 100  # truncated
        assert results[5]["message"]["text"] == ""
        assert results[2]["locations"][0]["physicalLocation"]["artifactLocation"] == {
            "uri": "/b.txt"
        }
        assert w.supports_streaming is False

    def test_empty_sarif(self, tmp_path):
        out = tmp_path / "r.sarif"
        SarifWriter(str(out)).finalize(metadata={"ignored": 1})
        run = json.loads(out.read_text(encoding="utf-8"))["runs"][0]
        assert run["tool"]["driver"]["rules"] == []
        assert run["results"] == []

    def test_write_failure_raises_output_error(self, bad_path):
        with pytest.raises(OutputError, match="Failed to write SARIF output"):
            SarifWriter(bad_path).finalize()


# ---------------------------------------------------------------------------
# Base class + factory
# ---------------------------------------------------------------------------


class TestOutputWriterBase:
    def test_abstract_cannot_be_instantiated(self, tmp_path):
        with pytest.raises(TypeError):
            OutputWriter(str(tmp_path / "x"))  # type: ignore[abstract]

    def test_default_optional_accessors(self, tmp_path):
        class Minimal(OutputWriter):
            def write_match(self, match):
                pass

            def finalize(self, metadata=None):
                pass

            @property
            def supports_streaming(self):
                return False

        w = Minimal(str(tmp_path / "x"), include_header=False)
        assert w.get_writer() is None
        assert w.file_handle is None
        assert w.include_header is False


class TestCreateOutputWriter:
    @pytest.mark.parametrize(
        ("fmt", "cls"),
        [
            ("json", JsonWriter),
            ("streaming-json", StreamingJsonWriter),
            ("jsonl", JsonlWriter),
            ("xlsx", XlsxWriter),
            ("html", HtmlWriter),
            ("sarif", SarifWriter),
            ("statistics", PrivacyStatisticsWriter),
            ("csv", CsvWriter),
        ],
    )
    def test_known_formats(self, tmp_path, fmt, cls):
        w = create_output_writer(fmt, str(tmp_path / f"out.{fmt}"))
        assert type(w) is cls
        w.finalize()

    @pytest.mark.parametrize("fmt", ["yaml", "", "CSV", "JSON", "parquet"])
    def test_unknown_or_miscased_format_silently_falls_back_to_csv(self, tmp_path, fmt):
        """Documents current behaviour: no error, CSV is produced for any unknown name.

        Note that the lookup is case-sensitive, so ``"JSON"`` also yields CSV.
        """
        out = tmp_path / "out.dat"
        w = create_output_writer(fmt, str(out))
        assert type(w) is CsvWriter
        w.finalize()
        assert out.read_text(encoding="utf-8").startswith("Match,File,Type")

    def test_include_header_is_propagated(self, tmp_path):
        out = tmp_path / "out.csv"
        w = create_output_writer("csv", str(out), include_header=False)
        assert w.include_header is False
        w.finalize()
        assert out.read_bytes() == b""

    def test_factory_propagates_output_error(self, bad_path):
        with pytest.raises(OutputError):
            create_output_writer("jsonl", bad_path)
