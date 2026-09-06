"""Tests for core.scan_reporting: post-scan logging, console summary, output
finalisation, statistics output and analytics finalisation.

All tests build a *real* ``ApplicationContext``/``Config``/``Statistics`` and a
real ``logging.Logger`` (captured via ``caplog``); console output is captured
via ``capsys`` and files are written under ``tmp_path`` only.
"""

from __future__ import annotations

import datetime
import json
import logging
import os
from argparse import Namespace

import pytest
import typer

from core import constants, scan_reporting
from core.config import Config
from core.context import ApplicationContext
from core.exceptions import OutputError
from core.matches import PiiMatch, PiiMatchContainer
from core.scanner import ScanResult
from core.statistics import Statistics
from core.statistics_aggregator import StatisticsAggregator
from core.writers import JsonWriter, OutputWriter

LOGGER_NAME = "tests.scan_reporting"

START = datetime.datetime(2026, 1, 2, 3, 4, 5)
END = datetime.datetime(2026, 1, 2, 3, 4, 15)  # 10 s later


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


class RecordingWriter(OutputWriter):
    """Non-streaming test double that records written matches and can be told
    to fail on finalize."""

    def __init__(self, file_path: str = "unused", fail: bool = False):
        super().__init__(file_path)
        self.written: list[PiiMatch] = []
        self.finalized_with: dict | None = None
        self.fail = fail

    def write_match(self, match: PiiMatch) -> None:
        self.written.append(match)

    def finalize(self, metadata: dict | None = None) -> None:
        if self.fail:
            raise OutputError("disk full")
        self.finalized_with = metadata

    @property
    def supports_streaming(self) -> bool:
        return False


def _match(file: str, type_: str, severity: str | None = None, **kw) -> PiiMatch:
    return PiiMatch(text="x", file=file, type=type_, severity=severity, **kw)


@pytest.fixture
def logger():
    lg = logging.getLogger(LOGGER_NAME)
    lg.setLevel(logging.DEBUG)
    return lg


@pytest.fixture
def make_context(tmp_path, logger):
    def _make(
        *,
        matches: list[PiiMatch] | None = None,
        output_writer: OutputWriter | None = None,
        timed: bool = True,
        translate=None,
        **config_kwargs,
    ) -> ApplicationContext:
        cfg_kwargs = {"path": str(tmp_path), "use_regex": True, "logger": logger}
        cfg_kwargs.update(config_kwargs)
        config = Config(**cfg_kwargs)
        stats = Statistics()
        if timed:
            stats.start_time = START
            stats.end_time = END
        container = PiiMatchContainer()
        container.pii_matches.extend(matches or [])
        ctx = ApplicationContext(
            config=config,
            logger=logger,
            statistics=stats,
            match_container=container,
            output_writer=output_writer,
            output_format="json" if output_writer else "csv",
        )
        if translate is not None:
            ctx.translate_func = translate
        return ctx

    return _make


# ---------------------------------------------------------------------------
# compute_file_risk_scores
# ---------------------------------------------------------------------------


class TestComputeFileRiskScores:
    def test_empty_container(self, make_context):
        ctx = make_context()
        scores, by_file = scan_reporting.compute_file_risk_scores(ctx.match_container)
        assert scores == {}
        assert by_file == {}

    def test_scores_and_grouping(self, make_context):
        matches = [
            _match("a.txt", "NER_PERSON"),
            _match("a.txt", "REGEX_IBAN"),
            _match("b.txt", "REGEX_IPV4"),
            _match("b.txt", "REGEX_IPV4"),
            _match("c.txt", ""),  # empty type is ignored for risk purposes
        ]
        ctx = make_context(matches=matches)

        scores, by_file = scan_reporting.compute_file_risk_scores(ctx.match_container)

        assert scores == {"a.txt": "CRITICAL", "b.txt": "LOW", "c.txt": "NONE"}
        assert [m.type for m in by_file["a.txt"]] == ["NER_PERSON", "REGEX_IBAN"]
        assert len(by_file["b.txt"]) == 2
        assert len(by_file["c.txt"]) == 1


# ---------------------------------------------------------------------------
# build_output_metadata
# ---------------------------------------------------------------------------


class TestBuildOutputMetadata:
    def test_full_metadata(self, make_context, tmp_path):
        matches = [
            _match("low.txt", "REGEX_IPV4"),
            _match("crit.txt", "REGEX_CREDIT_CARD"),
            _match("crit.txt", "REGEX_CREDIT_CARD"),
            _match("crit.txt", "REGEX_EMAIL"),
            _match("high.txt", "REGEX_IBAN"),
        ]
        ctx = make_context(matches=matches, use_ner=True, use_ollama=True)
        ctx.statistics.add_file_found(".txt")
        ctx.statistics.add_file_found(".txt")
        ctx.statistics.add_file_found(".pdf")
        ctx.statistics.add_file_processed()
        ctx.statistics.matches_found = 5
        ctx.statistics.add_error("read_error")
        errors = {"read_error": ["broken.pdf"], "timeout": []}
        scores, by_file = scan_reporting.compute_file_risk_scores(ctx.match_container)

        meta = scan_reporting.build_output_metadata(ctx, errors, scores, by_file)

        assert meta["start_time"] == START.isoformat()
        assert meta["end_time"] == END.isoformat()
        assert meta["duration_seconds"] == pytest.approx(10.0)
        assert meta["path"] == str(tmp_path)
        assert meta["methods"] == {
            "regex": True,
            "ner": True,
            "spacy_ner": False,
            "ollama": True,
            "openai_compatible": False,
            "multimodal": False,
            "pydantic_ai": False,
        }
        assert meta["total_files"] == 3
        assert meta["analyzed_files"] == 1
        assert meta["matches_found"] == 5
        assert meta["error_count"] == 1
        assert meta["statistics"]["files_scanned"] == 3
        # Sorted by count, descending
        assert list(meta["file_extensions"].items()) == [(".txt", 2), (".pdf", 1)]
        assert meta["errors"] == [
            {"type": "read_error", "files": ["broken.pdf"]},
            {"type": "timeout", "files": []},
        ]
        # Risk scores ordered by severity, highest first
        assert list(meta["file_risk_scores"]) == ["crit.txt", "high.txt", "low.txt"]
        crit = meta["file_risk_scores"]["crit.txt"]
        assert crit["risk_level"] == "CRITICAL"
        assert crit["match_count"] == 3
        assert sorted(crit["pii_types"]) == ["REGEX_CREDIT_CARD", "REGEX_EMAIL"]
        assert meta["file_risk_scores"]["low.txt"]["match_count"] == 1

    def test_without_timing_information(self, make_context):
        ctx = make_context(timed=False)
        meta = scan_reporting.build_output_metadata(ctx, {}, {}, {})
        assert meta["start_time"] is None
        assert meta["end_time"] is None
        assert meta["errors"] == []
        assert meta["file_risk_scores"] == {}

    def test_risk_score_for_unknown_level_sorts_last(self, make_context):
        ctx = make_context()
        scores = {"weird.txt": "BOGUS", "ok.txt": "LOW"}
        meta = scan_reporting.build_output_metadata(ctx, {}, scores, {})
        assert list(meta["file_risk_scores"]) == ["ok.txt", "weird.txt"]
        assert meta["file_risk_scores"]["weird.txt"]["match_count"] == 0


# ---------------------------------------------------------------------------
# write_output
# ---------------------------------------------------------------------------


class TestWriteOutput:
    def test_streaming_writer_only_finalizes(self, make_context, tmp_path):
        out = tmp_path / "findings.json"
        writer = JsonWriter(str(out))
        ctx = make_context(matches=[_match("a", "REGEX_EMAIL")], output_writer=writer)

        scan_reporting.write_output(ctx, {"path": "p"}, None)

        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["metadata"] == {"path": "p"}
        # Streaming writers get matches during the scan, not from write_output.
        assert data["findings"] == []
        assert not (tmp_path / "findings.json.findings.tmp").exists()

    def test_non_streaming_writer_receives_all_matches(self, make_context):
        writer = RecordingWriter()
        matches = [
            _match("a", "REGEX_EMAIL", "MEDIUM"),
            _match("b", "REGEX_IBAN", "HIGH"),
            _match("c", "REGEX_IPV4", None),
        ]
        ctx = make_context(matches=matches, output_writer=writer)

        scan_reporting.write_output(ctx, {"k": 1}, None)

        assert writer.written == matches
        assert writer.finalized_with == {"k": 1}

    def test_min_severity_filters_non_streaming_output(self, make_context):
        writer = RecordingWriter()
        matches = [
            _match("a", "REGEX_IPV4", "LOW"),
            _match("b", "REGEX_EMAIL", "MEDIUM"),
            _match("c", "REGEX_IBAN", "HIGH"),
            _match("d", "REGEX_SSN_US", "CRITICAL"),
            _match("e", "REGEX_EMAIL", None),  # unclassified -> filtered
        ]
        ctx = make_context(matches=matches, output_writer=writer, min_severity="HIGH")

        scan_reporting.write_output(ctx, {}, None)

        assert [m.file for m in writer.written] == ["c", "d"]

    def test_unknown_min_severity_disables_filter(self, make_context):
        writer = RecordingWriter()
        matches = [_match("a", "REGEX_IPV4", "LOW"), _match("e", "REGEX_EMAIL", None)]
        ctx = make_context(
            matches=matches, output_writer=writer, min_severity="NOT_A_LEVEL"
        )

        scan_reporting.write_output(ctx, {}, None)

        assert len(writer.written) == 2

    def test_output_error_logs_and_exits(self, make_context, caplog):
        writer = RecordingWriter(fail=True)
        ctx = make_context(output_writer=writer)

        with (
            caplog.at_level(logging.ERROR, logger=LOGGER_NAME),
            pytest.raises(typer.Exit) as exc_info,
        ):
            scan_reporting.write_output(ctx, {}, None)

        assert exc_info.value.exit_code == constants.EXIT_GENERAL_ERROR == 1
        assert any(
            r.levelno == logging.ERROR
            and "Failed to write output: disk full" in r.getMessage()
            for r in caplog.records
        )

    def test_no_writer_closes_csv_handle(self, make_context, tmp_path):
        ctx = make_context()
        handle = open(tmp_path / "legacy.csv", "w", encoding="utf-8")
        try:
            assert not handle.closed
            scan_reporting.write_output(ctx, {}, handle)
            assert handle.closed
        finally:
            if not handle.closed:
                handle.close()

    def test_no_writer_no_handle_is_noop(self, make_context):
        ctx = make_context()
        scan_reporting.write_output(ctx, {}, None)  # must not raise


# ---------------------------------------------------------------------------
# log_scan_results
# ---------------------------------------------------------------------------


class TestLogScanResults:
    def _messages(self, caplog):
        return [r.getMessage() for r in caplog.records]

    def test_basic_sections(self, make_context, caplog):
        ctx = make_context()
        ctx.statistics.add_file_found(".txt")
        ctx.statistics.add_file_found(".txt")
        ctx.statistics.add_file_found(".pdf")
        ctx.statistics.add_file_processed()
        errors = {"read_error": ["a.pdf", "b.pdf"]}

        with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
            scan_reporting.log_scan_results(ctx, errors)

        msgs = self._messages(caplog)
        assert "Statistics" in msgs
        assert "Findings" in msgs
        assert "Errors" in msgs
        assert "Skipped Files" not in msgs
        assert "Skipped Content" not in [m.strip() for m in msgs]
        assert "NER Statistics" not in [m.strip() for m in msgs]
        # Extensions sorted descending by count
        ext_lines = [m for m in msgs if "Dateien" in m]
        assert ext_lines[0].split(":")[0].strip() == ".txt"
        assert ext_lines[1].split(":")[0].strip() == ".pdf"
        assert any("TOTAL: 3 files" in m and "QUALIFIED: 1 files" in m for m in msgs)
        assert "\tread_error" in msgs
        assert "\t\ta.pdf" in msgs
        assert "\t\tb.pdf" in msgs
        assert any(f"Analysis finished at {END}" == m for m in msgs)
        assert any("0.1 analyzed files per second" in m for m in msgs)

    def test_skipped_files_and_content(self, make_context, caplog):
        ctx = make_context()
        ctx.statistics.add_skip("sqlite_blob_undecodable", 3)
        ctx.statistics.add_skip("llm_schema_mismatch", 7)
        result = ScanResult()
        result.record_skipped("too_large", "big.bin")
        result.record_skipped("too_large", "huge.bin")
        result.record_skipped("password_protected", "secret.pdf")

        with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
            scan_reporting.log_scan_results(ctx, {}, scan_result=result)

        msgs = self._messages(caplog)
        assert "Skipped Files" in msgs
        assert "\ttoo_large: 2 file(s)" in msgs
        assert "\t\tbig.bin" in msgs
        assert "\tpassword_protected: 1 file(s)" in msgs
        assert "\t\tsecret.pdf" in msgs
        assert "\nSkipped Content" in msgs
        idx_llm = msgs.index("\tllm_schema_mismatch: 7")
        idx_sql = msgs.index("\tsqlite_blob_undecodable: 3")
        assert idx_llm < idx_sql  # sorted by count, descending

    def test_scan_result_without_skips_omits_section(self, make_context, caplog):
        ctx = make_context()
        with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
            scan_reporting.log_scan_results(ctx, {}, scan_result=ScanResult())
        assert "Skipped Files" not in self._messages(caplog)

    def test_ner_statistics_with_errors(self, make_context, caplog):
        ctx = make_context(use_ner=True)
        ns = ctx.statistics.ner_stats
        ns.total_chunks_processed = 4
        ns.total_entities_found = 9
        ns.total_processing_time = 2.0
        ns.entities_by_type = {"PERSON": 6, "LOCATION": 3}
        ns.errors = 2

        with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
            scan_reporting.log_scan_results(ctx, {})

        msgs = self._messages(caplog)
        assert "\nNER Statistics" in msgs
        assert "Chunks processed: 4" in msgs
        assert "Entities found: 9" in msgs
        assert "Total NER processing time: 2.00s" in msgs
        assert "Average time per chunk: 0.500s" in msgs
        assert "Entities by type:" in msgs
        assert msgs.index("  PERSON: 6") < msgs.index("  LOCATION: 3")
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert [r.getMessage() for r in warnings] == ["NER errors encountered: 2"]

    def test_ner_statistics_without_entities_or_errors(self, make_context, caplog):
        ctx = make_context(use_ner=True)
        ctx.statistics.ner_stats.total_chunks_processed = 1

        with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
            scan_reporting.log_scan_results(ctx, {})

        msgs = self._messages(caplog)
        assert "\nNER Statistics" in msgs
        assert "Entities by type:" not in msgs
        assert not [r for r in caplog.records if r.levelno == logging.WARNING]

    def test_ner_statistics_skipped_when_ner_disabled(self, make_context, caplog):
        ctx = make_context(use_ner=False)
        ctx.statistics.ner_stats.total_chunks_processed = 10

        with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
            scan_reporting.log_scan_results(ctx, {})

        assert "\nNER Statistics" not in self._messages(caplog)

    def test_uses_translation_function(self, make_context, caplog):
        ctx = make_context(translate=lambda s: f"[de] {s}")
        with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
            scan_reporting.log_scan_results(ctx, {})
        assert "[de] Statistics" in self._messages(caplog)


# ---------------------------------------------------------------------------
# print_console_summary
# ---------------------------------------------------------------------------


class TestPrintConsoleSummary:
    def test_json_summary(self, make_context, capsys):
        ctx = make_context()
        ctx.statistics.total_files_found = 10
        ctx.statistics.files_processed = 5
        ctx.statistics.matches_found = 3
        ctx.statistics.add_error("x")
        ctx.statistics.add_skip("blob", 2)
        errors = {"x": ["f1", "f2"], "y": []}
        scores = {"a.txt": "HIGH"}

        scan_reporting.print_console_summary(
            ctx, errors, scores, {}, "/out/findings.csv", "/out/", "json"
        )

        data = json.loads(capsys.readouterr().out)
        assert data["start_time"] == START.isoformat()
        assert data["end_time"] == END.isoformat()
        assert data["duration_seconds"] == pytest.approx(10.0)
        assert data["statistics"] == {
            "files_scanned": 10,
            "files_analyzed": 5,
            "matches_found": 3,
            "errors": 1,
            "throughput_files_per_sec": 0.5,
        }
        assert data["output_file"] == "/out/findings.csv"
        assert data["output_directory"] == "/out/"
        assert data["errors_summary"] == {"x": 2, "y": 0}
        assert data["skipped_content"] == {"blob": 2}
        assert data["file_risk_scores"] == scores

    def test_json_summary_minimal(self, make_context, capsys):
        ctx = make_context(timed=False)
        ctx.output_file_path = "/ctx/path.json"

        scan_reporting.print_console_summary(
            ctx, {}, {}, {}, "/fallback", "/o/", "json"
        )

        data = json.loads(capsys.readouterr().out)
        assert data["start_time"] is None
        assert data["end_time"] is None
        assert data["errors_summary"] == {}
        assert data["skipped_content"] == {}
        # context.output_file_path takes precedence over the argument
        assert data["output_file"] == "/ctx/path.json"

    def test_human_summary_full(self, make_context, capsys):
        matches = [
            _match("crit.txt", "NER_PERSON"),
            _match("crit.txt", "REGEX_IBAN"),
            _match("high.txt", "NER_POLITICAL"),
            _match("high.txt", "NER_PERSON"),
            _match("low.txt", "REGEX_IPV4"),
            _match("med.txt", "REGEX_EMAIL"),
        ]
        ctx = make_context(matches=matches)
        ctx.statistics.total_files_found = 1234
        ctx.statistics.files_processed = 1000
        ctx.statistics.matches_found = 6
        ctx.statistics.add_skip("blob", 4)
        ctx.statistics.add_skip("schema", 9)
        errors = {"read_error": ["a", "b", "c"]}
        scores, by_file = scan_reporting.compute_file_risk_scores(ctx.match_container)

        scan_reporting.print_console_summary(
            ctx, errors, scores, by_file, "/out/x.csv", "/out/"
        )

        out = capsys.readouterr().out
        assert "Analysis Summary" in out
        assert "Started:     2026-01-02 03:04:05" in out
        assert "Finished:    2026-01-02 03:04:15" in out
        assert "Duration:    0:00:10" in out
        assert "Files scanned:      1,234" in out
        assert "Files analyzed:     1,000" in out
        assert "Matches found:      6" in out
        assert "Errors:             0" in out
        assert "Throughput:         100.0 files/sec" in out
        assert "Errors Summary:" in out
        assert "read_error: 3 files" in out
        assert "Skipped Content Summary:" in out
        assert out.index("schema: 9") < out.index("blob: 4")
        assert "File Risk Assessment:" in out
        assert "CRITICAL: 1 files" in out
        assert "HIGH: 1 files" in out
        assert "MEDIUM: 1 files" in out
        assert "LOW: 1 files" in out
        assert "Highest risk files:" in out
        assert "[CRITICAL] crit.txt (2 findings: NER_PERSON, REGEX_IBAN)" in out
        assert "[HIGH] high.txt (2 findings: NER_PERSON, NER_POLITICAL)" in out
        assert "[LOW] low.txt" not in out
        assert "Recommended actions:" in out
        assert "! 1 files with CRITICAL risk - immediate review recommended" in out
        assert "! 1 files with HIGH risk - review recommended" in out
        assert "Output file: /out/x.csv" in out
        assert "Output directory: /out/" in out

    def test_human_summary_minimal(self, make_context, capsys):
        ctx = make_context(timed=False)

        scan_reporting.print_console_summary(ctx, {}, {}, {}, "/o/f.csv", "/o/")

        out = capsys.readouterr().out
        assert "Started:" not in out
        assert "Finished:" not in out
        assert "Duration:    0:00:00" in out
        assert "Errors Summary:" not in out
        assert "Skipped Content Summary:" not in out
        assert "File Risk Assessment:" not in out
        assert "Recommended actions:" not in out
        assert "Output file: /o/f.csv" in out

    def test_human_summary_low_risk_only(self, make_context, capsys):
        ctx = make_context()
        scores = {"a.txt": "LOW", "b.txt": "MEDIUM", "c.txt": "NONE"}

        scan_reporting.print_console_summary(ctx, {}, scores, {}, "/o/f", "/o/")

        out = capsys.readouterr().out
        assert "File Risk Assessment:" in out
        assert "LOW: 1 files" in out
        assert "MEDIUM: 1 files" in out
        assert "NONE" not in out  # NONE is never listed
        assert "Highest risk files:" not in out
        assert "Recommended actions:" not in out

    def test_human_summary_lists_at_most_five_top_files(self, make_context, capsys):
        scores = {f"f{i}.txt": "HIGH" for i in range(8)}
        ctx = make_context()

        scan_reporting.print_console_summary(ctx, {}, scores, {}, "/o/f", "/o/")

        out = capsys.readouterr().out
        assert out.count("[HIGH] f") == 5
        assert "HIGH: 8 files" in out
        assert "! 8 files with HIGH risk" in out
        assert "CRITICAL risk" not in out

    def test_human_summary_prefers_context_output_path(self, make_context, capsys):
        ctx = make_context()
        ctx.output_file_path = "/ctx/out.json"
        scan_reporting.print_console_summary(ctx, {}, {}, {}, "/arg/out.json", "/o/")
        assert "Output file: /ctx/out.json" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# write_statistics_output
# ---------------------------------------------------------------------------


class TestWriteStatisticsOutput:
    def _aggregator(self, strict: bool = False) -> StatisticsAggregator:
        agg = StatisticsAggregator(strict=strict)
        agg.add_match(
            PiiMatch(
                text="x@y.de",
                file="/data/a.txt",
                type="REGEX_EMAIL",
                engine="regex",
                ner_score=0.9,
            )
        )
        return agg

    def test_none_aggregator_writes_nothing(self, make_context, tmp_path):
        ctx = make_context()
        out_dir = str(tmp_path) + os.sep
        scan_reporting.write_statistics_output(ctx, Namespace(), None, out_dir, "slug")
        assert list(tmp_path.iterdir()) == []

    def test_default_path_and_content(self, make_context, tmp_path, caplog):
        ctx = make_context()
        ctx.statistics.total_files_found = 4
        ctx.statistics.files_processed = 2
        ctx.statistics.matches_found = 5
        out_dir = str(tmp_path) + os.sep
        args = Namespace(statistics_output=None, statistics_strict=False)

        with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
            scan_reporting.write_statistics_output(
                ctx, args, self._aggregator(), out_dir, "scan-1"
            )

        stats_file = tmp_path / "scan-1_statistics.json"
        assert stats_file.exists()
        data = json.loads(stats_file.read_text(encoding="utf-8"))
        meta = data["metadata"]
        assert meta["scan_id"] == "scan-1"
        assert meta["start_time"] == START.isoformat()
        assert meta["end_time"] == END.isoformat()
        assert meta["duration_seconds"] == 10.0
        assert meta["scan_path"] == str(tmp_path)
        assert meta["detection_methods"]["regex"] is True
        assert meta["detection_methods"]["ner"] is False
        assert meta["total_files_scanned"] == 4
        assert meta["total_files_analyzed"] == 2
        assert meta["total_matches_found"] == 5
        assert meta["statistics_strict"] is False
        perf = data["performance_metrics"]
        assert perf["files_per_second"] == 0.2
        assert perf["matches_per_second"] == 0.5
        assert perf["processing_time_seconds"] == 10.0
        assert "ner_statistics" not in perf
        assert data["statistics_by_module"]["regex"]["total_matches"] == 1
        assert any(
            f"Privacy-focused statistics written to: {stats_file}" == r.getMessage()
            for r in caplog.records
        )

    def test_explicit_output_path_strict_and_ner(self, make_context, tmp_path):
        ctx = make_context(use_ner=True, timed=False)
        ns = ctx.statistics.ner_stats
        ns.total_chunks_processed = 3
        ns.total_entities_found = 6
        ns.total_processing_time = 1.0
        ns.errors = 1
        target = tmp_path / "custom" / "stats.json"
        target.parent.mkdir()
        args = Namespace(statistics_output=str(target), statistics_strict=True)

        scan_reporting.write_statistics_output(
            ctx, args, self._aggregator(strict=True), str(tmp_path) + os.sep, "slug"
        )

        assert not (tmp_path / "slug_statistics.json").exists()
        data = json.loads(target.read_text(encoding="utf-8"))
        assert data["metadata"]["scan_path"] is None
        assert data["metadata"]["statistics_strict"] is True
        assert data["metadata"]["start_time"] is None
        assert data["metadata"]["end_time"] is None
        assert data["performance_metrics"]["ner_statistics"] == {
            "chunks_processed": 3,
            "entities_found": 6,
            "avg_time_per_chunk": 0.333,
            "errors": 1,
        }
        # Never-started scan: duration is clamped to 1 ms, so matches/s is 0
        assert data["performance_metrics"]["matches_per_second"] == 0

    def test_args_without_statistics_attributes(self, make_context, tmp_path):
        ctx = make_context()
        scan_reporting.write_statistics_output(
            ctx, object(), self._aggregator(), str(tmp_path) + os.sep, "s"
        )
        data = json.loads((tmp_path / "s_statistics.json").read_text())
        assert data["metadata"]["statistics_strict"] is False

    def test_output_error_is_logged_not_raised(self, make_context, tmp_path, caplog):
        ctx = make_context()
        # A directory path cannot be opened for writing -> OSError -> OutputError
        args = Namespace(statistics_output=str(tmp_path), statistics_strict=False)

        with caplog.at_level(logging.ERROR, logger=LOGGER_NAME):
            scan_reporting.write_statistics_output(
                ctx, args, self._aggregator(), str(tmp_path) + os.sep, "s"
            )

        assert any(
            "Failed to write statistics output" in r.getMessage()
            and r.levelno == logging.ERROR
            for r in caplog.records
        )


# ---------------------------------------------------------------------------
# finalize_analytics
# ---------------------------------------------------------------------------


class FakeAnalyticsStore:
    def __init__(self, fail: bool = False):
        self.calls: list[tuple[str, dict]] = []
        self.fail = fail
        self.closed = False

    def complete_session(self, **kw):
        if self.fail:
            raise RuntimeError("db locked")
        self.calls.append(("complete_session", kw))

    def record_engine_stats(self, **kw):
        self.calls.append(("record_engine_stats", kw))

    def record_file_type_stats(self, **kw):
        self.calls.append(("record_file_type_stats", kw))

    def close(self):
        self.closed = True


class TestFinalizeAnalytics:
    def test_no_store_or_session_is_noop(self, make_context, logger):
        ctx = make_context()
        store = FakeAnalyticsStore()
        scan_reporting.finalize_analytics(None, "sid", ctx, logger)
        scan_reporting.finalize_analytics(store, None, ctx, logger)
        assert store.calls == []
        assert store.closed is False

    def test_records_everything_and_closes(self, make_context, logger):
        ctx = make_context()
        ctx.statistics.total_files_found = 7
        ctx.statistics.files_processed = 6
        ctx.statistics.matches_found = 3
        ctx.statistics.add_error("e")
        ctx.statistics.matches_by_engine = {"regex": 2, "gliner": 1}
        ctx.statistics.extension_counts = {".txt": 5, ".pdf": 2}
        store = FakeAnalyticsStore()

        scan_reporting.finalize_analytics(store, "sid-1", ctx, logger)

        assert store.calls[0] == (
            "complete_session",
            {
                "session_id": "sid-1",
                "total_files": 7,
                "files_processed": 6,
                "total_matches": 3,
                "total_errors": 1,
                "duration_sec": pytest.approx(10.0),
            },
        )
        engine_calls = [c[1] for c in store.calls if c[0] == "record_engine_stats"]
        assert engine_calls == [
            {"session_id": "sid-1", "engine": "regex", "matches_found": 2},
            {"session_id": "sid-1", "engine": "gliner", "matches_found": 1},
        ]
        ext_calls = [c[1] for c in store.calls if c[0] == "record_file_type_stats"]
        assert ext_calls == [
            {"session_id": "sid-1", "extension": ".txt", "files_scanned": 5},
            {"session_id": "sid-1", "extension": ".pdf", "files_scanned": 2},
        ]
        assert store.closed is True

    def test_store_failure_is_logged_as_warning(self, make_context, logger, caplog):
        ctx = make_context()
        store = FakeAnalyticsStore(fail=True)

        with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
            scan_reporting.finalize_analytics(store, "sid", ctx, logger)

        assert store.closed is False
        assert any(
            r.levelno == logging.WARNING
            and "Failed to finalize analytics session: db locked" in r.getMessage()
            for r in caplog.records
        )
