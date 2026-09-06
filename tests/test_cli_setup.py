"""Tests for core.cli_setup: logger setup, telemetry opt-out, config creation
and the legacy argparse ``setup()`` path.

The double-underscore helpers are module-level functions, so they are *not*
name-mangled at definition time. They are, however, mangled when referenced
from inside a class body (``cli_setup.__setup_logger`` would become
``cli_setup._TestX__setup_logger``), hence the module-level aliases below.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from argparse import Namespace

import pytest

from core import cli_setup, constants
from core.config import Config
from core.writers import CsvWriter, JsonWriter

setup_logger = cli_setup.__setup_logger
setup_args = cli_setup.__setup_args
setup_lang = cli_setup.__setup_lang
check_telemetry_settings = cli_setup.__check_telemetry_settings

PACKAGE_LOGGER = logging.getLogger("core")


@pytest.fixture(autouse=True)
def _restore_package_logger():
    """``__setup_logger`` attaches handlers to the shared ``core`` logger;
    detach (and close) whatever a test added so tests stay independent."""
    before_handlers = list(PACKAGE_LOGGER.handlers)
    before_level = PACKAGE_LOGGER.level
    yield
    for h in list(PACKAGE_LOGGER.handlers):
        if h not in before_handlers:
            PACKAGE_LOGGER.removeHandler(h)
            h.close()
    PACKAGE_LOGGER.setLevel(before_level)


def _new_handlers(before: list[logging.Handler]) -> list[logging.Handler]:
    return [h for h in PACKAGE_LOGGER.handlers if h not in before]


# ---------------------------------------------------------------------------
# __setup_logger
# ---------------------------------------------------------------------------


class TestSetupLogger:
    def test_default_mode_file_and_console_at_info(self, tmp_path):
        before = list(PACKAGE_LOGGER.handlers)
        args = Namespace(verbose=False, quiet=False)

        logger = setup_logger(args, outslug="run1", output_dir=str(tmp_path))

        assert logger is PACKAGE_LOGGER
        assert logger.level == logging.INFO
        new = _new_handlers(before)
        assert len(new) == 2
        file_handlers = [h for h in new if isinstance(h, logging.FileHandler)]
        assert len(file_handlers) == 1
        assert file_handlers[0].baseFilename == str(tmp_path / "run1_log.txt")
        assert file_handlers[0].level == logging.INFO
        console = [h for h in new if not isinstance(h, logging.FileHandler)][0]
        assert console.level == logging.INFO

        logger.info("hello from test")
        logger.debug("invisible")
        for h in new:
            h.flush()
        content = (tmp_path / "run1_log.txt").read_text(encoding="utf-8")
        assert "INFO - hello from test" in content
        assert "invisible" not in content

    def test_verbose_mode_uses_debug(self, tmp_path):
        before = list(PACKAGE_LOGGER.handlers)
        args = Namespace(verbose=True, quiet=False)

        logger = setup_logger(args, outslug="v", output_dir=str(tmp_path))

        assert logger.level == logging.DEBUG
        new = _new_handlers(before)
        assert len(new) == 2
        assert all(h.level == logging.DEBUG for h in new)
        logger.debug("debug line")
        for h in new:
            h.flush()
        assert "DEBUG - debug line" in (tmp_path / "v_log.txt").read_text()

    def test_quiet_mode_only_file_handler_at_error(self, tmp_path):
        before = list(PACKAGE_LOGGER.handlers)
        args = Namespace(verbose=False, quiet=True)

        logger = setup_logger(args, outslug="q", output_dir=str(tmp_path))

        assert logger.level == logging.ERROR
        new = _new_handlers(before)
        assert len(new) == 1
        assert isinstance(new[0], logging.FileHandler)
        assert new[0].level == logging.ERROR

    def test_quiet_wins_over_verbose(self, tmp_path):
        args = Namespace(verbose=True, quiet=True)
        logger = setup_logger(args, outslug="qv", output_dir=str(tmp_path))
        assert logger.level == logging.ERROR

    def test_no_args_means_info_and_file_only(self, tmp_path):
        before = list(PACKAGE_LOGGER.handlers)

        logger = setup_logger(None, outslug="noargs", output_dir=str(tmp_path))

        assert logger.level == logging.INFO
        new = _new_handlers(before)
        assert len(new) == 1
        assert isinstance(new[0], logging.FileHandler)
        assert (tmp_path / "noargs_log.txt").exists()

    def test_output_dir_from_args_when_not_given(self, tmp_path):
        args = Namespace(verbose=False, quiet=True, output_dir=str(tmp_path))
        setup_logger(args, outslug="fromargs")
        assert (tmp_path / "fromargs_log.txt").exists()

    def test_explicit_output_dir_overrides_args(self, tmp_path):
        other = tmp_path / "other"
        other.mkdir()
        args = Namespace(verbose=False, quiet=True, output_dir=str(tmp_path))
        setup_logger(args, outslug="explicit", output_dir=str(other))
        assert (other / "explicit_log.txt").exists()
        assert not (tmp_path / "explicit_log.txt").exists()

    def test_trailing_separator_is_not_doubled(self, tmp_path):
        before = list(PACKAGE_LOGGER.handlers)
        setup_logger(None, outslug="sep", output_dir=str(tmp_path) + os.sep)
        fh = _new_handlers(before)[0]
        assert fh.baseFilename == str(tmp_path / "sep_log.txt")

    def test_falls_back_to_constants_output_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr(constants, "OUTPUT_DIR", str(tmp_path))
        args = Namespace(verbose=False, quiet=True, output_dir=None)
        setup_logger(args, outslug="const")
        assert (tmp_path / "const_log.txt").exists()

    def test_empty_slug_creates_bare_log_file(self, tmp_path):
        setup_logger(None, output_dir=str(tmp_path))
        assert (tmp_path / "_log.txt").exists()

    def test_missing_output_dir_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            setup_logger(None, outslug="x", output_dir=str(tmp_path / "missing"))


# ---------------------------------------------------------------------------
# __check_telemetry_settings
# ---------------------------------------------------------------------------


class TestCheckTelemetrySettings:
    def test_sets_opt_out_variables(self, monkeypatch):
        monkeypatch.delenv("HF_HUB_DISABLE_TELEMETRY", raising=False)
        monkeypatch.delenv("TORCH_DISABLE_TELEMETRY", raising=False)

        check_telemetry_settings()

        assert os.environ["HF_HUB_DISABLE_TELEMETRY"] == "1"
        assert os.environ["TORCH_DISABLE_TELEMETRY"] == "1"

    def test_does_not_override_existing_values(self, monkeypatch):
        monkeypatch.setenv("HF_HUB_DISABLE_TELEMETRY", "0")
        monkeypatch.setenv("TORCH_DISABLE_TELEMETRY", "custom")

        check_telemetry_settings()

        assert os.environ["HF_HUB_DISABLE_TELEMETRY"] == "0"
        assert os.environ["TORCH_DISABLE_TELEMETRY"] == "custom"


# ---------------------------------------------------------------------------
# __setup_lang
# ---------------------------------------------------------------------------


class TestSetupLang:
    def test_returns_callable_translator(self, monkeypatch):
        monkeypatch.setenv("LANGUAGE", "en")
        translate = setup_lang()
        assert callable(translate)
        assert translate("Statistics") == "Statistics"


# ---------------------------------------------------------------------------
# create_config
# ---------------------------------------------------------------------------


def _base_args(tmp_path, **overrides) -> Namespace:
    ns = Namespace(
        path=str(tmp_path),
        regex=True,
        ner=False,
        verbose=False,
        outname=None,
        whitelist=None,
        stop_count=None,
    )
    for k, v in overrides.items():
        setattr(ns, k, v)
    return ns


class TestCreateConfig:
    def test_minimal_namespace(self, tmp_path):
        logger = logging.getLogger("tests.cli_setup.create_config")
        args = _base_args(tmp_path, stop_count=5, outname="run")

        def translate(s):
            return f"t:{s}"

        config = cli_setup.create_config(args, logger, None, None, translate)

        assert isinstance(config, Config)
        assert config.path == str(tmp_path)
        assert config.scan.path == str(tmp_path)  # sub-config mirrored
        assert config.use_regex is True
        assert config.use_ner is False
        assert config.verbose is False
        assert config.stop_count == 5
        assert config.outname == "run"
        assert config.logger is logger
        assert config.csv_writer is None
        assert config.csv_file_handle is None
        assert config._("x") == "t:x"
        # Regex pattern compiled from config_types.json
        assert config.regex_pattern is not None
        assert config.regex_pattern.search("mail: user@example.com") is not None
        # No NER model is loaded when ner is off
        assert config.ner_model is None
        # Optional engine flags default to False when absent from args
        assert config.use_spacy_ner is False
        assert config.use_pydantic_ai is False
        assert config.magic_detection_fallback is True

    def test_engine_and_csv_arguments_are_forwarded(self, tmp_path):
        logger = logging.getLogger("tests.cli_setup.create_config")
        args = _base_args(
            tmp_path,
            regex=False,
            verbose=True,
            spacy_ner=True,
            spacy_model="de_core_news_sm",
            ollama=True,
            ollama_url="http://ollama.local:1",
            ollama_model="mymodel",
            openai_api_base="https://api.example/v1",
            openai_api_key="key",
            openai_model="gpt-x",
            multimodal=True,
            multimodal_model="vision-1",
            multimodal_timeout=12,
            pydantic_ai=True,
            pydantic_ai_provider="ollama",
            pydantic_ai_model="pm",
            pydantic_ai_api_key="pk",
            pydantic_ai_base_url="http://p",
            vector_search=True,
            vector_model="vm",
            vector_threshold=0.5,
            vector_save_index=str(tmp_path / "idx"),
            vector_load_index="",
            vector_index_no_text=True,
            use_magic_detection=True,
            magic_fallback=False,
        )
        csv_writer = object()
        csv_handle = object()

        config = cli_setup.create_config(
            args, logger, csv_writer, csv_handle, lambda s: s
        )

        assert config.use_regex is False
        assert config.verbose is True
        assert config.runtime.verbose is True
        assert config.use_spacy_ner is True
        assert config.spacy_model_name == "de_core_news_sm"
        assert config.use_ollama is True
        assert config.ollama_base_url == "http://ollama.local:1"
        assert config.ollama_model == "mymodel"
        assert config.openai_api_base == "https://api.example/v1"
        assert config.openai_api_key == "key"
        assert config.openai_model == "gpt-x"
        assert config.use_multimodal is True
        # multimodal_api_base / key not in args -> fall back to openai values
        assert config.multimodal_api_base == "https://api.example/v1"
        assert config.multimodal_api_key == "key"
        assert config.multimodal_model == "vision-1"
        assert config.multimodal_timeout == 12
        assert config.use_pydantic_ai is True
        assert config.pydantic_ai_provider == "ollama"
        assert config.pydantic_ai_model == "pm"
        assert config.pydantic_ai_api_key == "pk"
        assert config.pydantic_ai_base_url == "http://p"
        assert config.use_vector_search is True
        assert config.vector_model == "vm"
        assert config.vector_threshold == 0.5
        assert config.vector_save_index == str(tmp_path / "idx")
        assert config.vector_load_index is None  # empty string is falsy
        assert config.vector_index_store_text is False
        assert config.use_magic_detection is True
        assert config.magic_detection_fallback is False
        assert config.csv_writer is csv_writer
        assert config.csv_file_handle is csv_handle

    def test_runtime_settings_from_config_types(self, tmp_path):
        """Best-effort runtime limits are read from config_types.json."""
        logger = logging.getLogger("tests.cli_setup.create_config")
        config = cli_setup.create_config(
            _base_args(tmp_path), logger, None, None, lambda s: s
        )
        assert config.max_file_size_mb > 0
        assert config.max_processing_time_seconds > 0
        assert config.max_pending_futures > 0


# ---------------------------------------------------------------------------
# __setup_args (legacy argparse) -- kept light, this path is dead outside tests
# ---------------------------------------------------------------------------


def _argv(monkeypatch, *argv: str) -> None:
    monkeypatch.setattr(sys, "argv", ["pbd", *argv])


class TestSetupArgs:
    def test_defaults(self, monkeypatch, tmp_path):
        _argv(monkeypatch, "--path", str(tmp_path), "--regex")

        args = setup_args(lambda s: s)

        assert args.path == str(tmp_path)
        assert args.regex is True
        assert args.ner is False
        assert args.output_dir == "./output/"
        assert args.format == "csv"
        assert args.summary_format == "human"
        assert args.verbose is False
        assert args.quiet is False
        assert args.config is None
        assert args.outname is None
        assert args.stop_count is None
        assert args.magic_fallback is True

    def test_path_is_required(self, monkeypatch, capsys):
        _argv(monkeypatch, "--regex")
        with pytest.raises(SystemExit) as exc_info:
            setup_args(lambda s: s)
        assert exc_info.value.code == 2
        assert "--path" in capsys.readouterr().err

    def test_invalid_choice_is_rejected(self, monkeypatch, capsys):
        _argv(monkeypatch, "--path", ".", "--format", "yaml")
        with pytest.raises(SystemExit) as exc_info:
            setup_args(lambda s: s)
        assert exc_info.value.code == 2
        assert "invalid choice" in capsys.readouterr().err

    def test_version_flag(self, monkeypatch, capsys):
        _argv(monkeypatch, "--version")
        with pytest.raises(SystemExit) as exc_info:
            setup_args(lambda s: s)
        assert exc_info.value.code == 0
        assert "pbD Toolkit 1.0.0" in capsys.readouterr().out

    def test_config_file_fills_unset_values(self, monkeypatch, tmp_path):
        cfg = tmp_path / "cfg.json"
        cfg.write_text(json.dumps({"outname": "from-config", "stop_count": 3}))
        _argv(monkeypatch, "--path", str(tmp_path), "--config", str(cfg))

        args = setup_args(lambda s: s)

        assert args.outname == "from-config"
        assert args.stop_count == 3
        assert args.path == str(tmp_path)

    def test_cli_value_beats_config_file(self, monkeypatch, tmp_path):
        cfg = tmp_path / "cfg.json"
        cfg.write_text(json.dumps({"outname": "from-config"}))
        _argv(
            monkeypatch,
            "--path",
            str(tmp_path),
            "--outname",
            "from-cli",
            "--config",
            str(cfg),
        )

        args = setup_args(lambda s: s)

        assert args.outname == "from-cli"

    def test_missing_config_file_is_a_usage_error(self, monkeypatch, tmp_path, capsys):
        _argv(monkeypatch, "--path", ".", "--config", str(tmp_path / "nope.json"))
        with pytest.raises(SystemExit) as exc_info:
            setup_args(lambda s: s)
        assert exc_info.value.code == 2
        assert "Configuration file error" in capsys.readouterr().err

    def test_translate_func_is_used_for_help(self, monkeypatch, capsys):
        _argv(monkeypatch, "--help")
        with pytest.raises(SystemExit) as exc_info:
            setup_args(lambda s: f"XX{s}")
        assert exc_info.value.code == 0
        assert "XXpbD Toolkit" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# setup() (deprecated legacy entry point)
# ---------------------------------------------------------------------------


class TestSetup:
    def test_full_legacy_setup(self, monkeypatch, tmp_path):
        out_dir = tmp_path / "out"  # does not exist yet -> created by setup()
        monkeypatch.delenv("HF_HUB_DISABLE_TELEMETRY", raising=False)
        monkeypatch.setenv("LANGUAGE", "en")
        _argv(
            monkeypatch,
            "--path",
            str(tmp_path),
            "--regex",
            "--output-dir",
            str(out_dir),
            "--outname",
            'a/b\\c:d"e',
            "--format",
            "json",
            "--quiet",
        )

        with pytest.warns(DeprecationWarning, match="deprecated"):
            args, logger, translate, writer, output_file_path = cli_setup.setup()

        try:
            assert os.environ["HF_HUB_DISABLE_TELEMETRY"] == "1"
            assert args.path == str(tmp_path)
            assert callable(translate)
            assert logger is PACKAGE_LOGGER
            assert isinstance(writer, JsonWriter)
            assert out_dir.is_dir()
            assert output_file_path.startswith(str(out_dir) + os.sep)
            assert output_file_path.endswith("_findings.json")
            # Path-hostile characters in --outname are neutralised
            assert " a_b_c_d_e_findings.json" in output_file_path
            assert "/b" not in os.path.basename(output_file_path)
            slug = os.path.basename(output_file_path)[: -len("_findings.json")]
            assert (out_dir / f"{slug}_log.txt").exists()
        finally:
            writer.finalize(metadata={})

    def test_default_format_is_csv_with_header_flag(self, monkeypatch, tmp_path):
        _argv(
            monkeypatch,
            "--path",
            str(tmp_path),
            "--regex",
            "--output-dir",
            str(tmp_path) + os.sep,
            "--no-header",
            "--quiet",
        )

        with pytest.warns(DeprecationWarning):
            args, _logger, _t, writer, output_file_path = cli_setup.setup()

        try:
            assert isinstance(writer, CsvWriter)
            assert writer.include_header is False
            assert output_file_path.endswith("_findings.csv")
            # Without --outname the slug is exactly the timestamp.
            slug = os.path.basename(output_file_path)[: -len("_findings.csv")]
            assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}-\d{2}-\d{2}", slug)
        finally:
            writer.finalize()
