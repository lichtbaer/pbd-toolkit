"""Tests for core.diff: loading scan result files and diffing two result sets."""

from __future__ import annotations

import json

import pytest

from core.diff import _finding_key, compute_diff, load_findings


def _f(file: str, type_: str, text: str, severity: str | None = "MEDIUM") -> dict:
    d = {"file": file, "type": type_, "text": text}
    if severity is not None:
        d["severity"] = severity
    return d


# ---------------------------------------------------------------------------
# load_findings
# ---------------------------------------------------------------------------


class TestLoadFindings:
    def test_missing_file_raises(self, tmp_path):
        missing = tmp_path / "missing.json"
        with pytest.raises(FileNotFoundError, match="File not found"):
            load_findings(str(missing))

    def test_json_with_findings_key(self, tmp_path):
        p = tmp_path / "scan.json"
        payload = {"metadata": {"path": "/x"}, "findings": [_f("a", "T", "1")]}
        p.write_text(json.dumps(payload), encoding="utf-8")

        assert load_findings(str(p)) == [_f("a", "T", "1")]

    def test_json_bare_list(self, tmp_path):
        p = tmp_path / "scan.json"
        p.write_text(json.dumps([_f("a", "T", "1"), _f("b", "U", "2")]))

        result = load_findings(str(p))
        assert len(result) == 2
        assert result[1]["file"] == "b"

    def test_json_dict_without_findings_is_empty(self, tmp_path):
        p = tmp_path / "scan.json"
        p.write_text(json.dumps({"metadata": {}}))
        assert load_findings(str(p)) == []

    def test_json_scalar_document_is_empty(self, tmp_path):
        p = tmp_path / "scan.json"
        p.write_text("42")
        assert load_findings(str(p)) == []

    def test_malformed_json_raises(self, tmp_path):
        p = tmp_path / "scan.json"
        p.write_text("{not valid", encoding="utf-8")
        with pytest.raises(json.JSONDecodeError):
            load_findings(str(p))

    def test_jsonl_skips_blank_and_metadata_lines(self, tmp_path):
        p = tmp_path / "scan.jsonl"
        lines = [
            json.dumps({"_metadata": {"version": 1}}),
            "",
            "   ",
            json.dumps(_f("a", "T", "1")),
            json.dumps(_f("b", "U", "2")),
            "",
        ]
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")

        result = load_findings(str(p))
        assert result == [_f("a", "T", "1"), _f("b", "U", "2")]

    def test_jsonl_empty_file(self, tmp_path):
        p = tmp_path / "scan.jsonl"
        p.write_text("", encoding="utf-8")
        assert load_findings(str(p)) == []

    def test_jsonl_malformed_line_raises(self, tmp_path):
        p = tmp_path / "scan.jsonl"
        p.write_text(json.dumps(_f("a", "T", "1")) + "\n{oops\n", encoding="utf-8")
        with pytest.raises(json.JSONDecodeError):
            load_findings(str(p))

    def test_jsonl_suffix_must_be_exact(self, tmp_path):
        """A ``.JSONL`` (upper-case) suffix is treated as plain JSON, so the
        line-delimited content fails to parse. Documents current behaviour."""
        p = tmp_path / "scan.JSONL"
        p.write_text(
            json.dumps(_f("a", "T", "1")) + "\n" + json.dumps(_f("b", "T", "2"))
        )
        with pytest.raises(json.JSONDecodeError):
            load_findings(str(p))

    def test_csv_is_not_supported_and_fails_as_json(self, tmp_path):
        """The diff loader only understands JSON/JSONL; a CSV export is parsed
        as JSON and therefore raises. Documents current behaviour."""
        p = tmp_path / "scan.csv"
        p.write_text("file,type,text\na,T,1\n", encoding="utf-8")
        with pytest.raises(json.JSONDecodeError):
            load_findings(str(p))

    def test_unicode_content_roundtrip(self, tmp_path):
        p = tmp_path / "scan.json"
        p.write_text(
            json.dumps({"findings": [_f("ü.txt", "NER_PERSON", "Jörg Müller")]}),
            encoding="utf-8",
        )
        assert load_findings(str(p))[0]["text"] == "Jörg Müller"


# ---------------------------------------------------------------------------
# _finding_key
# ---------------------------------------------------------------------------


class TestFindingKey:
    def test_key_uses_file_type_text(self):
        assert _finding_key(_f("f", "T", "x")) == ("f", "T", "x")

    def test_missing_fields_default_to_empty_string(self):
        assert _finding_key({}) == ("", "", "")
        assert _finding_key({"file": "f"}) == ("f", "", "")

    def test_extra_fields_are_ignored(self):
        a = _finding_key({"file": "f", "type": "T", "text": "x", "severity": "LOW"})
        b = _finding_key({"file": "f", "type": "T", "text": "x", "engine": "regex"})
        assert a == b


# ---------------------------------------------------------------------------
# compute_diff
# ---------------------------------------------------------------------------


class TestComputeDiff:
    def test_both_empty(self):
        result = compute_diff([], [])
        assert result["summary"] == {
            "old_total": 0,
            "new_total": 0,
            "added": 0,
            "removed": 0,
            "unchanged": 0,
        }
        assert result["added_by_severity"] == {}
        assert result["removed_by_severity"] == {}
        assert result["added_findings"] == []
        assert result["removed_findings"] == []

    def test_added_removed_unchanged(self):
        old = [
            _f("a.txt", "REGEX_EMAIL", "x@y.de", "MEDIUM"),
            _f("b.txt", "REGEX_IBAN", "DE00", "HIGH"),
            _f("c.txt", "NER_PERSON", "Max", "MEDIUM"),
        ]
        new = [
            _f("a.txt", "REGEX_EMAIL", "x@y.de", "MEDIUM"),  # unchanged
            _f("d.txt", "REGEX_CREDIT_CARD", "4111", "CRITICAL"),  # added
            _f("e.txt", "REGEX_EMAIL", "z@y.de", "MEDIUM"),  # added
        ]

        result = compute_diff(old, new)

        assert result["summary"] == {
            "old_total": 3,
            "new_total": 3,
            "added": 2,
            "removed": 2,
            "unchanged": 1,
        }
        assert result["added_findings"] == [
            _f("d.txt", "REGEX_CREDIT_CARD", "4111", "CRITICAL"),
            _f("e.txt", "REGEX_EMAIL", "z@y.de", "MEDIUM"),
        ]
        assert result["removed_findings"] == [
            _f("b.txt", "REGEX_IBAN", "DE00", "HIGH"),
            _f("c.txt", "NER_PERSON", "Max", "MEDIUM"),
        ]
        assert result["added_by_severity"] == {"CRITICAL": 1, "MEDIUM": 1}
        assert result["removed_by_severity"] == {"HIGH": 1, "MEDIUM": 1}

    def test_identical_sets_have_no_changes(self):
        findings = [_f("a", "T", "1"), _f("b", "U", "2")]
        result = compute_diff(findings, list(findings))
        assert result["summary"]["added"] == 0
        assert result["summary"]["removed"] == 0
        assert result["summary"]["unchanged"] == 2

    def test_output_is_sorted_by_key(self):
        new = [_f("z", "T", "1"), _f("a", "T", "1"), _f("a", "S", "9")]
        result = compute_diff([], new)
        assert [(f["file"], f["type"]) for f in result["added_findings"]] == [
            ("a", "S"),
            ("a", "T"),
            ("z", "T"),
        ]

    def test_same_key_with_different_severity_is_unchanged(self):
        """Identity is (file, type, text); a severity change alone is not a diff."""
        old = [_f("a", "T", "1", "LOW")]
        new = [_f("a", "T", "1", "CRITICAL")]
        result = compute_diff(old, new)
        assert result["summary"]["unchanged"] == 1
        assert result["summary"]["added"] == 0
        assert result["summary"]["removed"] == 0

    def test_duplicates_collapse_but_totals_count_raw_lists(self):
        old = [_f("a", "T", "1"), _f("a", "T", "1")]
        new = [_f("a", "T", "1"), _f("a", "T", "1"), _f("a", "T", "1")]
        result = compute_diff(old, new)
        assert result["summary"]["old_total"] == 2
        assert result["summary"]["new_total"] == 3
        assert result["summary"]["unchanged"] == 1
        assert result["summary"]["added"] == 0

    def test_last_duplicate_wins(self):
        """When two findings share a key, the later dict is the one reported."""
        new = [
            {"file": "a", "type": "T", "text": "1", "engine": "first"},
            {"file": "a", "type": "T", "text": "1", "engine": "second"},
        ]
        result = compute_diff([], new)
        assert result["added_findings"] == [new[1]]

    def test_missing_severity_is_counted_as_unknown(self):
        result = compute_diff(
            [_f("r", "T", "0", severity=None)],
            [_f("a", "T", "1", severity=None), _f("b", "T", "2", "LOW")],
        )
        assert result["added_by_severity"] == {"UNKNOWN": 1, "LOW": 1}
        assert result["removed_by_severity"] == {"UNKNOWN": 1}

    def test_text_is_case_sensitive(self):
        result = compute_diff([_f("a", "T", "abc")], [_f("a", "T", "ABC")])
        assert result["summary"]["added"] == 1
        assert result["summary"]["removed"] == 1
        assert result["summary"]["unchanged"] == 0

    def test_end_to_end_via_files(self, tmp_path):
        old_p = tmp_path / "old.json"
        new_p = tmp_path / "new.jsonl"
        old_p.write_text(
            json.dumps({"findings": [_f("a", "T", "1", "LOW"), _f("b", "T", "2")]})
        )
        new_p.write_text(
            json.dumps({"_metadata": {}})
            + "\n"
            + json.dumps(_f("b", "T", "2"))
            + "\n"
            + json.dumps(_f("c", "T", "3", "HIGH"))
            + "\n"
        )

        result = compute_diff(load_findings(str(old_p)), load_findings(str(new_p)))

        assert result["summary"] == {
            "old_total": 2,
            "new_total": 2,
            "added": 1,
            "removed": 1,
            "unchanged": 1,
        }
        assert result["added_findings"][0]["file"] == "c"
        assert result["removed_findings"][0]["file"] == "a"
        assert result["added_by_severity"] == {"HIGH": 1}
        assert result["removed_by_severity"] == {"LOW": 1}
