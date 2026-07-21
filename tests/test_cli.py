"""Tests for CLI commands using Typer CliRunner."""

import json
import os
import stat
from pathlib import Path

from typer.testing import CliRunner

from core import constants
from core.cli import app

runner = CliRunner()


class TestCliVersion:
    """Tests for --version option."""

    def test_version_option(self):
        """Test --version prints version and exits."""
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "pbd-toolkit" in result.output

    def test_version_short_flag(self):
        """Test -V prints version."""
        result = runner.invoke(app, ["-V"])
        assert result.exit_code == 0
        assert "pbd-toolkit" in result.output


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

    def test_scan_no_detection_method_enabled(self, temp_dir):
        """Test scan without any engine flag fails with EXIT_INVALID_ARGUMENTS."""
        result = runner.invoke(
            app,
            ["scan", temp_dir, "--quiet"],
            catch_exceptions=False,
        )
        assert result.exit_code == constants.EXIT_INVALID_ARGUMENTS
        assert "detection method" in result.output.lower()

    def test_scan_json_format_writes_output_file(self, temp_dir):
        """Test scan --format json produces a findings file with the expected shape."""
        (Path(temp_dir) / "test.txt").write_text("Contact: user@example.com")
        out_dir = Path(temp_dir) / "out"
        result = runner.invoke(
            app,
            [
                "scan",
                temp_dir,
                "--regex",
                "--quiet",
                "--format",
                "json",
                "--output-dir",
                str(out_dir),
                "--outname",
                "results",
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        out_files = list(out_dir.glob("*results_findings.json"))
        assert len(out_files) == 1
        data = json.loads(out_files[0].read_text())
        assert "metadata" in data
        assert "findings" in data

    def test_scan_with_exclude_pattern(self, temp_dir):
        """Test scan --exclude skips matching files."""
        (Path(temp_dir) / "keep.txt").write_text("user@example.com")
        (Path(temp_dir) / "skip.txt").write_text("skip@example.com")
        out_dir = Path(temp_dir) / "out"
        result = runner.invoke(
            app,
            [
                "scan",
                temp_dir,
                "--regex",
                "--quiet",
                "--exclude",
                "skip.txt",
                "--format",
                "json",
                "--output-dir",
                str(out_dir),
                "--outname",
                "results",
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        out_files = list(out_dir.glob("*results_findings.json"))
        assert len(out_files) == 1
        data = json.loads(out_files[0].read_text())
        files_hit = {f["file"] for f in data["findings"]}
        assert not any("skip.txt" in f for f in files_hit)


class TestCliQuery:
    """Tests for query command."""

    def test_query_help(self):
        result = runner.invoke(app, ["query", "--help"])
        assert result.exit_code == 0
        assert "query" in result.output.lower()

    def test_query_no_text_provided(self, temp_dir):
        """Neither positional query text nor --query given."""
        index_path = os.path.join(temp_dir, "myindex")
        result = runner.invoke(app, ["query", index_path], catch_exceptions=False)
        assert result.exit_code == constants.EXIT_INVALID_ARGUMENTS
        assert "provide query text" in result.output.lower()

    def test_query_missing_index_metadata(self, temp_dir):
        """Index metadata file does not exist."""
        index_path = os.path.join(temp_dir, "nonexistent_index")
        result = runner.invoke(
            app, ["query", index_path, "some text"], catch_exceptions=False
        )
        assert result.exit_code == constants.EXIT_INVALID_ARGUMENTS
        assert "metadata file not found" in result.output.lower()

    def test_query_indexer_unavailable(self, temp_dir):
        """sentence-transformers is not installed in the test env: configuration error."""
        index_path = os.path.join(temp_dir, "myindex")
        Path(index_path + ".meta").write_text("{}")
        result = runner.invoke(
            app, ["query", index_path, "--query", "test"], catch_exceptions=False
        )
        assert result.exit_code == constants.EXIT_CONFIGURATION_ERROR


class TestCliEvaluate:
    """Tests for evaluate command."""

    DATASET = "eval/datasets/synthetic_de.json"

    def test_evaluate_help(self):
        result = runner.invoke(app, ["evaluate", "--help"])
        assert result.exit_code == 0

    def test_evaluate_dataset_not_found(self):
        result = runner.invoke(
            app, ["evaluate", "/nonexistent/dataset.json"], catch_exceptions=False
        )
        assert result.exit_code == constants.EXIT_INVALID_ARGUMENTS

    def test_evaluate_human_output(self):
        result = runner.invoke(
            app,
            ["evaluate", self.DATASET, "--engines", "regex"],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        assert "micro" in result.output.lower()

    def test_evaluate_json_output(self):
        result = runner.invoke(
            app,
            ["evaluate", self.DATASET, "--engines", "regex", "--format", "json"],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert "micro" in payload

    def test_evaluate_fail_under_triggers_gate(self):
        result = runner.invoke(
            app,
            [
                "evaluate",
                self.DATASET,
                "--engines",
                "regex",
                "--fail-under",
                "0.999",
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == constants.EXIT_GENERAL_ERROR
        assert "quality gate failed" in result.output.lower()


class TestCliEvalExtraction:
    """Tests for eval-extraction command."""

    MANIFEST = "eval/datasets/extraction/manifest.json"

    def test_eval_extraction_help(self):
        result = runner.invoke(app, ["eval-extraction", "--help"])
        assert result.exit_code == 0

    def test_eval_extraction_manifest_not_found(self):
        result = runner.invoke(
            app,
            ["eval-extraction", "/nonexistent/manifest.json"],
            catch_exceptions=False,
        )
        assert result.exit_code == constants.EXIT_INVALID_ARGUMENTS

    def test_eval_extraction_human_output(self):
        result = runner.invoke(
            app, ["eval-extraction", self.MANIFEST], catch_exceptions=False
        )
        assert result.exit_code == 0
        assert "extraction recall" in result.output.lower()

    def test_eval_extraction_json_output(self):
        result = runner.invoke(
            app,
            ["eval-extraction", self.MANIFEST, "--format", "json"],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert "recall" in payload


class TestCliDiff:
    """Tests for diff command."""

    def _write(self, path, findings):
        Path(path).write_text(json.dumps({"findings": findings}))

    def test_diff_help(self):
        result = runner.invoke(app, ["diff", "--help"])
        assert result.exit_code == 0

    def test_diff_old_file_missing(self, temp_dir):
        new_file = os.path.join(temp_dir, "new.json")
        self._write(new_file, [])
        result = runner.invoke(
            app,
            ["diff", os.path.join(temp_dir, "missing.json"), new_file],
            catch_exceptions=False,
        )
        assert result.exit_code == constants.EXIT_INVALID_ARGUMENTS
        assert "old file" in result.output.lower()

    def test_diff_new_file_invalid_json(self, temp_dir):
        old_file = os.path.join(temp_dir, "old.json")
        new_file = os.path.join(temp_dir, "new.json")
        self._write(old_file, [])
        Path(new_file).write_text("{not valid json")
        result = runner.invoke(
            app, ["diff", old_file, new_file], catch_exceptions=False
        )
        assert result.exit_code == constants.EXIT_INVALID_ARGUMENTS
        assert "new file" in result.output.lower()

    def test_diff_human_output_shows_added_and_removed(self, temp_dir):
        old_file = os.path.join(temp_dir, "old.json")
        new_file = os.path.join(temp_dir, "new.json")
        self._write(
            old_file,
            [{"file": "a.txt", "type": "EMAIL", "text": "a@x.com", "severity": "LOW"}],
        )
        self._write(
            new_file,
            [
                {
                    "file": "b.txt",
                    "type": "IBAN",
                    "text": "DE00",
                    "severity": "CRITICAL",
                }
            ],
        )
        result = runner.invoke(
            app, ["diff", old_file, new_file], catch_exceptions=False
        )
        assert result.exit_code == 0
        assert "+1" in result.output
        assert "-1" in result.output

    def test_diff_json_output(self, temp_dir):
        old_file = os.path.join(temp_dir, "old.json")
        new_file = os.path.join(temp_dir, "new.json")
        self._write(old_file, [])
        self._write(new_file, [])
        result = runner.invoke(
            app,
            ["diff", old_file, new_file, "--format", "json"],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["summary"]["added"] == 0


class TestCliReport:
    """Tests for report command."""

    def test_report_help(self):
        result = runner.invoke(app, ["report", "--help"])
        assert result.exit_code == 0

    def test_report_db_not_found(self, temp_dir):
        db_path = os.path.join(temp_dir, "missing.db")
        result = runner.invoke(app, ["report", "--db", db_path], catch_exceptions=False)
        assert result.exit_code == constants.EXIT_INVALID_ARGUMENTS
        assert "not found" in result.output.lower()

    def test_report_human_output_with_seeded_db(self, temp_dir):
        from analytics.store import AnalyticsStore

        db_path = os.path.join(temp_dir, "analytics.db")
        store = AnalyticsStore(db_path=db_path)
        sid = store.create_session(scan_path=temp_dir)
        store.complete_session(
            session_id=sid,
            total_files=5,
            files_processed=5,
            total_matches=2,
            total_errors=0,
            duration_sec=1.2,
        )
        store.record_finding(
            session_id=sid,
            file_path=os.path.join(temp_dir, "f.txt"),
            pii_type="REGEX_EMAIL",
            engine="regex",
            severity="MEDIUM",
            confidence=0.9,
        )
        store.close()

        result = runner.invoke(app, ["report", "--db", db_path], catch_exceptions=False)
        assert result.exit_code == 0
        assert "analytics report" in result.output.lower()

    def test_report_json_output_with_seeded_db(self, temp_dir):
        from analytics.store import AnalyticsStore

        db_path = os.path.join(temp_dir, "analytics.db")
        store = AnalyticsStore(db_path=db_path)
        store.create_session(scan_path=temp_dir)
        store.close()

        result = runner.invoke(
            app,
            ["report", "--db", db_path, "--format", "json"],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["database"] == db_path


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

    def test_doctor_json_output(self):
        result = runner.invoke(app, ["doctor", "--json"], catch_exceptions=False)
        assert result.exit_code in (
            constants.EXIT_SUCCESS,
            constants.EXIT_CONFIGURATION_ERROR,
        )
        payload = json.loads(result.output)
        assert "ok" in payload
        assert "issues" in payload


class TestCliServe:
    """Tests for serve command."""

    def test_serve_help(self):
        result = runner.invoke(app, ["serve", "--help"])
        assert result.exit_code == 0
        assert "api" in result.output.lower()

    def test_serve_missing_api_extra(self):
        """Without fastapi/uvicorn installed, serve exits gracefully (not a raw traceback)."""
        result = runner.invoke(app, ["serve"], catch_exceptions=False)
        assert result.exit_code != 0
        assert "pip install 'pbd-toolkit[api]'" in result.output


class TestCliInstallHook:
    """Tests for install-hook command."""

    def test_install_hook_help(self):
        result = runner.invoke(app, ["install-hook", "--help"])
        assert result.exit_code == 0

    def test_install_hook_not_a_git_repo(self, temp_dir):
        result = runner.invoke(
            app, ["install-hook", "--git-dir", temp_dir], catch_exceptions=False
        )
        assert result.exit_code == constants.EXIT_INVALID_ARGUMENTS
        assert "git repository" in result.output.lower()

    def test_install_hook_creates_executable_hook(self, temp_dir):
        hooks_dir = Path(temp_dir) / ".git" / "hooks"
        hooks_dir.mkdir(parents=True)
        result = runner.invoke(
            app, ["install-hook", "--git-dir", temp_dir], catch_exceptions=False
        )
        assert result.exit_code == 0
        hook_path = hooks_dir / "pre-commit"
        assert hook_path.exists()
        mode = os.stat(hook_path).st_mode
        assert mode & stat.S_IXUSR
        assert "installed at" in result.output.lower()

    def test_install_hook_existing_without_force_aborts(self, temp_dir):
        hooks_dir = Path(temp_dir) / ".git" / "hooks"
        hooks_dir.mkdir(parents=True)
        (hooks_dir / "pre-commit").write_text("#!/bin/sh\necho existing\n")
        result = runner.invoke(
            app,
            ["install-hook", "--git-dir", temp_dir],
            input="n\n",
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        assert "aborted" in result.output.lower()
        assert (hooks_dir / "pre-commit").read_text().startswith("#!/bin/sh\necho")


class TestCliTestPattern:
    """Tests for test-pattern command."""

    def test_test_pattern_help(self):
        result = runner.invoke(app, ["test-pattern", "--help"])
        assert result.exit_code == 0

    def test_test_pattern_detects_email(self):
        result = runner.invoke(
            app,
            ["test-pattern", "--text", "Contact me at test@example.com"],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        assert "test@example.com" in result.output

    def test_test_pattern_json_output(self):
        result = runner.invoke(
            app,
            [
                "test-pattern",
                "--text",
                "Contact me at test@example.com",
                "--format",
                "json",
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert isinstance(payload, list)
        assert any(m["type"] for m in payload)

    def test_test_pattern_no_input_text(self):
        result = runner.invoke(
            app, ["test-pattern", "--text", "   "], catch_exceptions=False
        )
        assert result.exit_code == constants.EXIT_INVALID_ARGUMENTS
        assert "no input text" in result.output.lower()

    def test_test_pattern_no_engine_enabled(self):
        result = runner.invoke(
            app,
            ["test-pattern", "--text", "hello", "--no-regex"],
            catch_exceptions=False,
        )
        assert result.exit_code == constants.EXIT_INVALID_ARGUMENTS
        assert "at least one engine" in result.output.lower()


class TestCliExportConfig:
    """Tests for export-config command."""

    def test_export_config_help(self):
        result = runner.invoke(app, ["export-config", "--help"])
        assert result.exit_code == 0

    def test_export_config_stdout_yaml(self):
        result = runner.invoke(app, ["export-config"], catch_exceptions=False)
        assert result.exit_code == 0
        assert "scan" in result.output.lower()

    def test_export_config_json_format(self):
        result = runner.invoke(
            app, ["export-config", "--format", "json"], catch_exceptions=False
        )
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert "scan" in payload
        assert "engine" in payload
        assert "output" in payload

    def test_export_config_writes_to_file(self, temp_dir):
        out_path = os.path.join(temp_dir, "exported.yaml")
        result = runner.invoke(app, ["export-config", out_path], catch_exceptions=False)
        assert result.exit_code == 0
        assert os.path.isfile(out_path)
        assert "exported to" in result.output.lower()

    def test_export_config_write_error(self):
        """Writing to a path inside a nonexistent directory triggers EXIT_GENERAL_ERROR."""
        result = runner.invoke(
            app,
            ["export-config", "/nonexistent_dir_xyz123/exported.yaml"],
            catch_exceptions=False,
        )
        assert result.exit_code == constants.EXIT_GENERAL_ERROR
