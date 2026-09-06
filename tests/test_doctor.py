"""Unit tests for ``core.doctor`` (run_doctor, check_api_connectivity, run_benchmark).

``tests/test_doctor_command.py`` only smoke-tests the CLI against the real
environment. Everything here is hermetic: the config_types payload is injected,
optional dependencies are faked through ``sys.modules``, the disk probe is
stubbed, and every HTTP call goes through a stubbed ``requests.get`` so no test
ever touches the network.
"""

from __future__ import annotations

import builtins
import json
import shutil
import sys
import types
from collections import namedtuple
from unittest.mock import Mock

import pytest
import requests
from typer.testing import CliRunner

import core.doctor as doctor_mod
import core.resources as resources_mod
from core import constants
from core.doctor import (
    DoctorIssue,
    DoctorReport,
    check_api_connectivity,
    run_benchmark,
    run_doctor,
)

# ---------------------------------------------------------------------------
# helpers / fixtures
# ---------------------------------------------------------------------------

MINIMAL_CFG: dict = {
    "settings": {},
    "regex": [
        {
            "label": "REGEX_EMAIL",
            "expression": r"[\w.]+@[\w.]+\.\w{2,}",
            "regex_compiled_pos": 0,
        },
        {"label": "REGEX_DIGITS", "expression": r"\b\d{4}\b", "regex_compiled_pos": 1},
    ],
    "ai-ner": [{"term": "person", "label": "NER_PERSON"}],
}


def _msgs(report: DoctorReport, level: str | None = None) -> list[str]:
    return [i.message for i in report.issues if level is None or i.level == level]


def _has(report: DoctorReport, fragment: str, level: str | None = None) -> bool:
    return any(fragment in m for m in _msgs(report, level))


def _fake_module(name: str, **attrs) -> types.ModuleType:
    mod = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(mod, key, value)
    return mod


DiskUsage = namedtuple("DiskUsage", "total used free")


@pytest.fixture
def cfg(monkeypatch):
    """Inject a deep copy of MINIMAL_CFG as the config_types payload."""
    data = json.loads(json.dumps(MINIMAL_CFG))
    monkeypatch.setattr(doctor_mod, "load_config_types", lambda: data)
    return data


@pytest.fixture
def no_optional_deps(monkeypatch):
    """Make torch/gliner/spacy look absent regardless of the host environment."""
    for name in ("torch", "gliner", "spacy"):
        monkeypatch.setitem(sys.modules, name, None)


@pytest.fixture
def no_network(monkeypatch):
    """Fail loudly if anything in a test reaches for ``requests.get``."""

    def _boom(*_a, **_kw):  # pragma: no cover - only hit on regressions
        raise AssertionError("unexpected network access")

    monkeypatch.setattr(requests, "get", _boom)


# ---------------------------------------------------------------------------
# run_doctor: config_types validation
# ---------------------------------------------------------------------------


class TestRunDoctorConfigValidation:
    def test_valid_config_reports_ok(self, cfg, no_optional_deps, no_network):
        report = run_doctor()

        assert report.ok is True
        assert report.details["regex_count"] == 2
        assert report.details["python_version"] == (
            f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        )
        assert _has(report, "All 2 regex pattern(s) compile successfully", "info")
        assert report.details["benchmark_run"] is False
        assert "api_endpoints_tested" not in report.details
        assert not _msgs(report, "error")

    def test_load_failure_short_circuits(self, monkeypatch, no_network):
        def _raise():
            raise FileNotFoundError("nope")

        monkeypatch.setattr(doctor_mod, "load_config_types", _raise)

        report = run_doctor()

        assert report.ok is False
        assert len(report.issues) == 1
        assert report.issues[0].level == "error"
        assert "Failed to load config_types.json: nope" in report.issues[0].message
        # Nothing else was probed.
        assert report.details == {}

    def test_missing_top_level_keys(self, monkeypatch, no_optional_deps, no_network):
        monkeypatch.setattr(doctor_mod, "load_config_types", lambda: {})

        report = run_doctor()

        errors = _msgs(report, "error")
        assert "Missing top-level key: 'settings'" in errors
        assert "Missing top-level key: 'regex'" in errors
        assert "Missing top-level key: 'ai-ner'" in errors
        assert "config['regex'] must be a list" in errors
        assert "config['ai-ner'] must be a list" in errors
        assert report.ok is False
        assert report.details["regex_count"] == 0
        assert not _has(report, "compile successfully")

    def test_regex_not_a_list_is_error_and_skipped(
        self, cfg, no_optional_deps, no_network
    ):
        cfg["regex"] = "not-a-list"

        report = run_doctor()

        assert "config['regex'] must be a list" in _msgs(report, "error")
        assert report.details["regex_count"] == 0
        assert report.ok is False

    def test_regex_entry_not_an_object(self, cfg, no_optional_deps, no_network):
        cfg["regex"] = [42]

        report = run_doctor()

        assert "regex[0] must be an object" in _msgs(report, "error")
        assert report.ok is False

    def test_regex_entry_missing_fields(self, cfg, no_optional_deps, no_network):
        cfg["regex"] = [{}]

        report = run_doctor()

        errors = _msgs(report, "error")
        assert "regex[0] missing/invalid 'label'" in errors
        assert "regex[0] missing/invalid 'expression'" in errors
        assert any(
            "regex[0] 'None': missing/invalid regex_compiled_pos" in w
            for w in _msgs(report, "warning")
        )
        assert report.ok is False

    def test_regex_empty_strings_are_invalid(self, cfg, no_optional_deps, no_network):
        cfg["regex"] = [{"label": "", "expression": "", "regex_compiled_pos": 0}]

        report = run_doctor()

        errors = _msgs(report, "error")
        assert "regex[0] missing/invalid 'label'" in errors
        assert "regex[0] missing/invalid 'expression'" in errors

    def test_invalid_regex_expression(self, cfg, no_optional_deps, no_network):
        cfg["regex"][1]["expression"] = "("

        report = run_doctor()

        assert any(
            "regex[1] 'REGEX_DIGITS': invalid regex" in e
            for e in _msgs(report, "error")
        )
        assert report.ok is False
        # The success summary must not be emitted when a pattern failed.
        assert not _has(report, "compile successfully")
        assert report.details["regex_count"] == 2

    def test_duplicate_and_mismatched_positions_are_warnings(
        self, cfg, no_optional_deps, no_network
    ):
        cfg["regex"][1]["regex_compiled_pos"] = 0  # duplicates index-0 entry

        report = run_doctor()

        warnings = _msgs(report, "warning")
        assert "Duplicate regex_compiled_pos=0 ('REGEX_DIGITS')" in warnings
        assert any(
            w.startswith("1 regex entries have regex_compiled_pos") for w in warnings
        )
        # Mapping problems are hygiene warnings, never hard failures.
        assert report.ok is True

    def test_non_int_position_is_warning(self, cfg, no_optional_deps, no_network):
        cfg["regex"][0]["regex_compiled_pos"] = "0"

        report = run_doctor()

        assert any(
            "regex[0] 'REGEX_EMAIL': missing/invalid regex_compiled_pos" in w
            for w in _msgs(report, "warning")
        )
        assert report.ok is True

    def test_combined_pattern_failure_is_error(self, cfg, no_optional_deps, no_network):
        # Each expression compiles alone, but the alternation redefines a group name.
        cfg["regex"] = [
            {"label": "A", "expression": "(?P<dup>a)", "regex_compiled_pos": 0},
            {"label": "B", "expression": "(?P<dup>b)", "regex_compiled_pos": 1},
        ]

        report = run_doctor()

        assert any(
            e.startswith("Combined regex failed to compile")
            for e in _msgs(report, "error")
        )
        assert report.ok is False
        # Individual compile check still passed, so the per-pattern summary is present.
        assert _has(report, "All 2 regex pattern(s) compile successfully")

    def test_python_too_old_is_error(
        self, cfg, monkeypatch, no_optional_deps, no_network
    ):
        VersionInfo = namedtuple("VersionInfo", "major minor micro")
        monkeypatch.setattr(sys, "version_info", VersionInfo(3, 9, 7))

        report = run_doctor()

        assert "Python 3.9.7 is too old. Python 3.10+ is required." in _msgs(
            report, "error"
        )
        assert report.details["python_version"] == "3.9.7"
        assert report.ok is False

    def test_multimodal_hint_always_present(self, cfg, no_optional_deps, no_network):
        report = run_doctor()
        assert _has(report, "OpenAI-compatible server", "info")

    @pytest.mark.skip(
        reason="repo-root/core config_types.json sync branch is known dead code: "
        "no config_types.json exists at the repository root"
    )
    def test_repo_root_config_sync_branch(self):  # pragma: no cover
        pass


# ---------------------------------------------------------------------------
# run_doctor: optional dependency probing
# ---------------------------------------------------------------------------


class TestRunDoctorDependencies:
    def test_installed_with_dunder_version(
        self, cfg, monkeypatch, no_optional_deps, no_network
    ):
        monkeypatch.setitem(
            sys.modules, "gliner", _fake_module("gliner", __version__="9.9.9")
        )

        report = run_doctor()

        assert "[OK] GLiNER NER (--ner): 'gliner' v9.9.9 installed ✓" in _msgs(
            report, "info"
        )
        assert report.details["dependencies"]["gliner"] == "v9.9.9"

    def test_installed_with_plain_version_attribute(
        self, cfg, monkeypatch, no_optional_deps, no_network
    ):
        monkeypatch.setitem(sys.modules, "spacy", _fake_module("spacy", version="3.7"))

        report = run_doctor()

        assert report.details["dependencies"]["spacy"] == "v3.7"
        assert _has(report, "'spacy' v3.7 installed")

    def test_installed_without_version(
        self, cfg, monkeypatch, no_optional_deps, no_network
    ):
        monkeypatch.setitem(sys.modules, "gliner", _fake_module("gliner"))

        report = run_doctor()

        assert report.details["dependencies"]["gliner"] == "installed"
        assert "[OK] GLiNER NER (--ner): 'gliner' installed ✓" in _msgs(report, "info")

    def test_missing_dependency_is_info_with_hint(
        self, cfg, no_optional_deps, no_network
    ):
        report = run_doctor()

        expected = (
            "[--] Optional dependency not installed for GLiNER NER (--ner): "
            "'gliner'. Install with: pip install gliner"
        )
        assert expected in _msgs(report, "info")
        assert report.details["dependencies"]["gliner"] == "not installed"
        # Missing optional dependencies never fail the doctor run.
        assert report.ok is True

    def test_import_raising_non_import_error_counts_as_missing(
        self, cfg, monkeypatch, no_optional_deps, no_network
    ):
        real_import = builtins.__import__

        def _import(name, *args, **kwargs):
            if name == "fastapi":
                raise RuntimeError("broken install")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", _import)

        report = run_doctor()

        assert report.details["dependencies"]["fastapi"] == "not installed"
        assert _has(report, "'fastapi'. Install with: pip install fastapi")

    def test_all_probed_modules_are_reported(self, cfg, no_optional_deps, no_network):
        report = run_doctor()

        expected = {
            "gliner",
            "spacy",
            "pydantic_ai",
            "requests",
            "pdfminer",
            "docx",
            "openpyxl",
            "bs4",
            "defusedxml",
            "PIL",
            "sentence_transformers",
            "magic",
            "fastapi",
            "yaml",
        }
        assert set(report.details["dependencies"]) == expected


# ---------------------------------------------------------------------------
# run_doctor: GPU + disk probes
# ---------------------------------------------------------------------------


class TestRunDoctorEnvironmentProbes:
    def test_gpu_detected(self, cfg, monkeypatch, no_optional_deps, no_network):
        cuda = types.SimpleNamespace(
            is_available=lambda: True, get_device_name=lambda idx: f"Fake GPU {idx}"
        )
        torch = _fake_module(
            "torch", cuda=cuda, version=types.SimpleNamespace(cuda="12.1")
        )
        monkeypatch.setitem(sys.modules, "torch", torch)

        report = run_doctor()

        assert report.details["gpu"] == {
            "available": True,
            "name": "Fake GPU 0",
            "cuda": "12.1",
        }
        assert _has(report, "GPU available: Fake GPU 0 (CUDA 12.1)", "info")

    def test_gpu_cuda_version_unknown(
        self, cfg, monkeypatch, no_optional_deps, no_network
    ):
        cuda = types.SimpleNamespace(
            is_available=lambda: True, get_device_name=lambda idx: "GPU"
        )
        torch = _fake_module(
            "torch", cuda=cuda, version=types.SimpleNamespace(cuda=None)
        )
        monkeypatch.setitem(sys.modules, "torch", torch)

        report = run_doctor()

        assert report.details["gpu"]["cuda"] == "unknown"

    def test_torch_present_without_gpu(
        self, cfg, monkeypatch, no_optional_deps, no_network
    ):
        cuda = types.SimpleNamespace(is_available=lambda: False)
        monkeypatch.setitem(sys.modules, "torch", _fake_module("torch", cuda=cuda))

        report = run_doctor()

        assert report.details["gpu"] == {"available": False}
        assert _has(report, "No GPU detected", "info")

    def test_torch_absent(self, cfg, no_optional_deps, no_network):
        report = run_doctor()

        assert report.details["gpu"] == {
            "available": False,
            "reason": "torch not installed",
        }
        assert _has(report, "PyTorch not installed", "info")

    def test_low_disk_space_is_warning(
        self, cfg, monkeypatch, no_optional_deps, no_network
    ):
        half_gb = int(0.5 * 1024**3)
        monkeypatch.setattr(
            shutil, "disk_usage", lambda _p: DiskUsage(10 * 1024**3, 0, half_gb)
        )

        report = run_doctor()

        assert "Low disk space in output directory: 0.5 GB free" in _msgs(
            report, "warning"
        )
        assert report.details["disk_free_gb"] == 0.5
        assert report.ok is True  # warning only

    def test_sufficient_disk_space_is_info(
        self, cfg, monkeypatch, no_optional_deps, no_network
    ):
        monkeypatch.setattr(
            shutil,
            "disk_usage",
            lambda _p: DiskUsage(100 * 1024**3, 0, int(42.26 * 1024**3)),
        )

        report = run_doctor()

        assert "Disk space in output directory: 42.3 GB free ✓" in _msgs(report, "info")
        assert report.details["disk_free_gb"] == 42.3

    def test_disk_probe_failure_is_swallowed(
        self, cfg, monkeypatch, no_optional_deps, no_network
    ):
        def _raise(_p):
            raise OSError("statvfs failed")

        monkeypatch.setattr(shutil, "disk_usage", _raise)

        report = run_doctor()

        assert "disk_free_gb" not in report.details
        assert not _has(report, "Disk space")
        assert report.ok is True


# ---------------------------------------------------------------------------
# run_doctor: optional connectivity + benchmark hooks
# ---------------------------------------------------------------------------


class TestRunDoctorOptionalSteps:
    def test_api_endpoints_are_probed_and_recorded(
        self, cfg, monkeypatch, no_optional_deps
    ):
        get = Mock(return_value=Mock(status_code=200))
        monkeypatch.setattr(requests, "get", get)

        report = run_doctor(api_endpoints={"llm": "http://localhost:1/v1"})

        assert report.details["api_endpoints_tested"] == ["llm"]
        assert _has(
            report, "API endpoint reachable: llm (http://localhost:1/v1) → HTTP 200"
        )
        get.assert_called_once_with("http://localhost:1/v1", timeout=5)

    def test_empty_endpoint_mapping_skips_probe(
        self, cfg, no_optional_deps, no_network
    ):
        report = run_doctor(api_endpoints={})
        assert "api_endpoints_tested" not in report.details

    def test_run_bench_flag_merges_benchmark_issues(
        self, cfg, monkeypatch, no_optional_deps, no_network
    ):
        monkeypatch.setattr(
            doctor_mod, "run_benchmark", lambda: [DoctorIssue("info", "bench-marker")]
        )

        report = run_doctor(run_bench=True)

        assert report.details["benchmark_run"] is True
        assert "bench-marker" in _msgs(report, "info")


# ---------------------------------------------------------------------------
# check_api_connectivity
# ---------------------------------------------------------------------------


class TestCheckApiConnectivity:
    def test_reachable_endpoint(self, monkeypatch):
        get = Mock(return_value=Mock(status_code=204))
        monkeypatch.setattr(requests, "get", get)

        issues = check_api_connectivity({"svc": "http://127.0.0.1:9/x"}, timeout=2)

        assert [(i.level, i.message) for i in issues] == [
            ("info", "API endpoint reachable: svc (http://127.0.0.1:9/x) → HTTP 204")
        ]
        get.assert_called_once_with("http://127.0.0.1:9/x", timeout=2)

    def test_unreachable_endpoint_is_warning(self, monkeypatch):
        monkeypatch.setattr(
            requests, "get", Mock(side_effect=ConnectionError("refused"))
        )

        issues = check_api_connectivity({"svc": "http://127.0.0.1:9/x"})

        assert len(issues) == 1
        assert issues[0].level == "warning"
        assert issues[0].message.startswith(
            "API endpoint NOT reachable: svc (http://127.0.0.1:9/x) — refused"
        )

    def test_mixed_results_preserve_order(self, monkeypatch):
        def _get(url, timeout):
            if "bad" in url:
                raise TimeoutError("slow")
            return Mock(status_code=200)

        monkeypatch.setattr(requests, "get", _get)

        issues = check_api_connectivity({"a": "http://ok", "b": "http://bad"})

        assert [i.level for i in issues] == ["info", "warning"]
        assert "slow" in issues[1].message

    def test_no_endpoints(self, no_network):
        assert check_api_connectivity({}) == []

    def test_requests_missing(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "requests", None)

        issues = check_api_connectivity({"svc": "http://127.0.0.1:9/x"})

        assert len(issues) == 1
        assert issues[0].level == "warning"
        assert "'requests' library not installed" in issues[0].message


# ---------------------------------------------------------------------------
# run_benchmark
# ---------------------------------------------------------------------------


@pytest.fixture
def bench_cfg(monkeypatch):
    """run_benchmark imports load_config_types from core.resources at call time."""
    data = json.loads(json.dumps(MINIMAL_CFG))
    monkeypatch.setattr(resources_mod, "load_config_types", lambda: data)
    return data


def _fake_gliner(entities=None, exc: Exception | None = None):
    class GLiNER:
        @classmethod
        def from_pretrained(cls, name):
            if exc is not None:
                raise exc
            inst = cls()
            inst.name = name
            return inst

        def predict_entities(self, text, labels, threshold):
            return entities or []

    return _fake_module("gliner", GLiNER=GLiNER)


def _fake_spacy(n_ents=1, load_exc: Exception | None = None):
    def load(model_name):
        if load_exc is not None:
            raise load_exc

        def nlp(text):
            return types.SimpleNamespace(ents=[object()] * n_ents)

        return nlp

    return _fake_module("spacy", load=load)


class TestRunBenchmark:
    def test_regex_on_tiny_corpus(self, tmp_path, bench_cfg, no_optional_deps):
        corpus = tmp_path / "corpus.txt"
        corpus.write_text(
            "Contact max@example.com or anna@example.org, ref 2024.", encoding="utf-8"
        )

        issues = run_benchmark(corpus.read_text(encoding="utf-8"))

        levels = {i.message.split(":")[0]: i for i in issues}
        regex_issue = levels["Benchmark regex"]
        assert regex_issue.level == "info"
        # Two e-mail addresses and one 4-digit token.
        assert regex_issue.message.startswith("Benchmark regex: 3 match(es) in ")
        assert regex_issue.message.endswith(" ms")
        assert "Benchmark GLiNER: skipped (not installed)" in [
            i.message for i in issues
        ]
        assert "Benchmark spaCy: skipped (not installed)" in [i.message for i in issues]
        assert all(i.level == "info" for i in issues)

    def test_regex_default_text(self, bench_cfg, no_optional_deps):
        issues = run_benchmark()
        assert any(
            m.startswith("Benchmark regex: 1 match(es)")
            for m in (i.message for i in issues)
        )

    def test_no_regex_entries_skips_regex_line(self, bench_cfg, no_optional_deps):
        bench_cfg["regex"] = []

        issues = run_benchmark("max@example.com")

        assert not any(i.message.startswith("Benchmark regex") for i in issues)
        assert len(issues) == 2

    def test_regex_failure_is_warning(self, bench_cfg, no_optional_deps):
        bench_cfg["regex"][0]["expression"] = "("

        issues = run_benchmark("x")

        regex_issue = next(i for i in issues if i.message.startswith("Benchmark regex"))
        assert regex_issue.level == "warning"
        assert regex_issue.message.startswith("Benchmark regex failed: ")

    def test_gliner_installed_without_labels(self, bench_cfg, monkeypatch):
        bench_cfg["ai-ner"] = []
        monkeypatch.setitem(sys.modules, "gliner", _fake_gliner())
        monkeypatch.setitem(sys.modules, "spacy", None)

        issues = run_benchmark("x")

        assert "Benchmark GLiNER: skipped (no labels configured)" in [
            i.message for i in issues
        ]

    def test_gliner_benchmark_runs_without_a_top_level_constants_module(
        self, bench_cfg, monkeypatch
    ):
        """Regression: run_benchmark used to do a bare ``import constants``.

        The module lives at ``core/constants.py``, so with GLiNER installed the
        benchmark could never reach the model and always reported
        "No module named 'constants'".
        """
        monkeypatch.setitem(sys.modules, "gliner", _fake_gliner(entities=[{"x": 1}]))
        monkeypatch.setitem(sys.modules, "spacy", None)
        monkeypatch.delitem(sys.modules, "constants", raising=False)

        issues = run_benchmark("x")

        gl = next(i for i in issues if "GLiNER" in i.message)
        assert gl.level == "info"
        assert gl.message.startswith("Benchmark GLiNER: 1 entity/entities in ")

    def test_gliner_success_when_constants_importable(self, bench_cfg, monkeypatch):
        monkeypatch.setitem(
            sys.modules, "gliner", _fake_gliner(entities=[{"a": 1}, {"b": 2}])
        )
        monkeypatch.setitem(sys.modules, "spacy", None)

        issues = run_benchmark("x")

        gl = next(i for i in issues if "GLiNER" in i.message)
        assert gl.level == "info"
        assert gl.message.startswith("Benchmark GLiNER: 2 entity/entities in ")

    def test_gliner_model_load_failure(self, bench_cfg, monkeypatch):
        monkeypatch.setitem(
            sys.modules, "gliner", _fake_gliner(exc=RuntimeError("no weights"))
        )
        monkeypatch.setitem(sys.modules, "spacy", None)

        issues = run_benchmark("x")

        gl = next(i for i in issues if "GLiNER" in i.message)
        assert gl.level == "warning"
        assert gl.message == "Benchmark GLiNER model run failed: no weights"

    def test_spacy_success_uses_default_model_name(self, bench_cfg, monkeypatch):
        monkeypatch.delattr(constants, "SPACY_MODEL_NAME", raising=False)
        monkeypatch.setitem(sys.modules, "gliner", None)
        monkeypatch.setitem(sys.modules, "spacy", _fake_spacy(n_ents=3))

        issues = run_benchmark("x")

        sp = next(i for i in issues if "spaCy" in i.message)
        assert sp.level == "info"
        assert sp.message.startswith(
            "Benchmark spaCy (de_core_news_lg): 3 entity/entities in "
        )

    def test_spacy_uses_configured_model_name(self, bench_cfg, monkeypatch):
        monkeypatch.setattr(constants, "SPACY_MODEL_NAME", "xx_tiny", raising=False)
        monkeypatch.setitem(sys.modules, "gliner", None)
        monkeypatch.setitem(sys.modules, "spacy", _fake_spacy(n_ents=0))

        issues = run_benchmark("x")

        sp = next(i for i in issues if "spaCy" in i.message)
        assert sp.message.startswith("Benchmark spaCy (xx_tiny): 0 entity/entities")

    def test_spacy_load_failure_is_warning(self, bench_cfg, monkeypatch):
        monkeypatch.setitem(sys.modules, "gliner", None)
        monkeypatch.setitem(
            sys.modules, "spacy", _fake_spacy(load_exc=OSError("model missing"))
        )

        issues = run_benchmark("x")

        sp = next(i for i in issues if "spaCy" in i.message)
        assert sp.level == "warning"
        assert sp.message == "Benchmark spaCy model run failed: model missing"


# ---------------------------------------------------------------------------
# CLI: --json / --strict semantics (run_doctor stubbed)
# ---------------------------------------------------------------------------


def _cli_report(ok: bool, levels: list[str]) -> DoctorReport:
    return DoctorReport(
        ok=ok,
        issues=[DoctorIssue(lvl, f"{lvl}-msg") for lvl in levels],
        details={"regex_count": 1},
    )


class TestDoctorCli:
    @pytest.fixture(autouse=True)
    def _cli_app(self):
        from core.cli import app

        self.app = app
        self.runner = CliRunner()

    def test_json_output_structure(self, monkeypatch):
        monkeypatch.setattr(
            "core.cli.run_doctor", lambda: _cli_report(True, ["info", "warning"])
        )

        result = self.runner.invoke(self.app, ["doctor", "--json"])

        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload == {
            "ok": True,
            "issues": [
                {"level": "info", "message": "info-msg"},
                {"level": "warning", "message": "warning-msg"},
            ],
            "details": {"regex_count": 1},
        }

    def test_human_output_lists_issues(self, monkeypatch):
        monkeypatch.setattr(
            "core.cli.run_doctor", lambda: _cli_report(True, ["info", "warning"])
        )

        result = self.runner.invoke(self.app, ["doctor"])

        assert result.exit_code == 0
        assert result.stdout.startswith("Doctor: ")
        assert "- INFO: info-msg" in result.stdout
        assert "- WARNING: warning-msg" in result.stdout

    def test_warning_without_strict_exits_zero(self, monkeypatch):
        monkeypatch.setattr(
            "core.cli.run_doctor", lambda: _cli_report(True, ["warning"])
        )

        result = self.runner.invoke(self.app, ["doctor"])

        assert result.exit_code == 0

    def test_warning_with_strict_exits_config_error(self, monkeypatch):
        monkeypatch.setattr(
            "core.cli.run_doctor", lambda: _cli_report(True, ["warning"])
        )

        result = self.runner.invoke(self.app, ["doctor", "--strict"])

        assert result.exit_code == constants.EXIT_CONFIGURATION_ERROR

    def test_strict_with_only_info_exits_zero(self, monkeypatch):
        monkeypatch.setattr("core.cli.run_doctor", lambda: _cli_report(True, ["info"]))

        result = self.runner.invoke(self.app, ["doctor", "--strict"])

        assert result.exit_code == 0

    def test_error_report_exits_config_error(self, monkeypatch):
        monkeypatch.setattr(
            "core.cli.run_doctor", lambda: _cli_report(False, ["error"])
        )

        result = self.runner.invoke(self.app, ["doctor"])

        assert result.exit_code == constants.EXIT_CONFIGURATION_ERROR
        assert result.stdout.startswith("Doctor: ")
        assert "- ERROR: error-msg" in result.stdout

    def test_error_report_with_json_still_prints_payload(self, monkeypatch):
        monkeypatch.setattr(
            "core.cli.run_doctor", lambda: _cli_report(False, ["error"])
        )

        result = self.runner.invoke(self.app, ["doctor", "--json"])

        assert result.exit_code == constants.EXIT_CONFIGURATION_ERROR
        assert json.loads(result.stdout)["ok"] is False
