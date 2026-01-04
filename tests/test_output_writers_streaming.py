"""Tests for streaming output writers (JSONL, XLSX)."""

from __future__ import annotations

import json

from matches import PiiMatch
from core.writers import create_output_writer


def test_jsonl_writer_streams_and_appends_metadata(tmp_path):
    out = tmp_path / "findings.jsonl"
    writer = create_output_writer("jsonl", str(out))

    writer.write_match(
        PiiMatch(
            text="user@example.com",
            file="/tmp/a.txt",
            type="REGEX_EMAIL",
            ner_score=None,
            engine="regex",
            metadata={},
        )
    )
    writer.finalize(metadata={"k": "v"})

    lines = out.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert first["text"] == "user@example.com"
    assert first["type"] == "REGEX_EMAIL"
    last = json.loads(lines[1])
    assert last["_metadata"]["k"] == "v"


def test_xlsx_writer_streams_rows(tmp_path):
    out = tmp_path / "findings.xlsx"
    writer = create_output_writer("xlsx", str(out))

    writer.write_match(
        PiiMatch(
            text="John Doe",
            file="/tmp/a.txt",
            type="NER_PERSON",
            ner_score=0.9,
            engine="gliner",
            metadata={},
        )
    )
    writer.finalize(metadata={"scan": "id"})

    import openpyxl

    wb = openpyxl.load_workbook(str(out), read_only=True, data_only=True)
    assert "Findings" in wb.sheetnames
    ws = wb["Findings"]
    rows = list(ws.iter_rows(values_only=True))
    # header + one row
    assert rows[0] == ("Match", "File", "Type", "Score", "Engine")
    assert rows[1][0] == "John Doe"
    assert "Metadata" in wb.sheetnames

