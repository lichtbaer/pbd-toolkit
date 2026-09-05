"""Tests for registry dependency injection through the scan pipeline (issue #78).

``FileProcessorRegistry`` and ``EngineRegistry`` are process-global mutable
state. ``snapshot()`` exists so a long-lived process can pin a stable set, but a
snapshot is only useful if the scan pipeline can actually be told to use one.
These tests cover that seam end to end: ``FileScanner``, ``TextProcessor``,
``ScanRunner`` (via ``ScanRequest``) and ``ScannerService``.

The injection proof throughout is an *empty* registry: a component wired to one
must find nothing, while the same component with the default (global) registry
finds the real processors. That distinguishes "the parameter is threaded
through" from "the parameter is accepted and ignored".
"""

from __future__ import annotations

import argparse
import logging

from core.config import Config
from core.engines.base import DetectionEngine
from core.engines.registry import EngineRegistry, EngineRegistrySnapshot
from core.matches import PiiMatchContainer
from core.processor import TextProcessor
from core.scan_runner import ScanRequest, ScanRunner
from core.scanner import FileScanner
from file_processors.registry import (
    FileProcessorRegistry,
    FileProcessorRegistrySnapshot,
)


def _empty_processor_registry() -> FileProcessorRegistrySnapshot:
    """A processor registry that claims nothing."""
    return FileProcessorRegistrySnapshot([], {})


def _empty_engine_registry() -> EngineRegistrySnapshot:
    """An engine registry with nothing registered."""
    return EngineRegistrySnapshot({})


def _make_regex_config(path: str, logger: logging.Logger) -> Config:
    """Build a regex-only :class:`Config` for *path* (mirrors test_scan_runner)."""
    args = argparse.Namespace(
        path=path,
        regex=True,
        ner=False,
        spacy_ner=False,
        ollama=False,
        openai_compatible=False,
        pydantic_ai=False,
        vector_search=False,
        multimodal=False,
        verbose=False,
        outname=None,
        whitelist=None,
        stop_count=None,
        deduplicate=False,
        incremental=False,
        text_chunk_size=0,
        text_chunk_overlap=200,
        context_chars=0,
        min_confidence=0.0,
        format="json",
        no_header=False,
        use_magic_detection=False,
        magic_fallback=True,
        cache_path=None,
    )
    return Config.from_args(
        args=args,
        logger=logger,
        csv_writer=None,
        csv_file_handle=None,
        translate_func=lambda x: x,
    )


class TestFileScannerRegistryInjection:
    """``FileScanner`` routes extension support checks through its registry."""

    def test_defaults_to_global_registry(self, mock_config):
        """Omitting the argument keeps the pre-existing global behaviour."""
        scanner = FileScanner(mock_config)
        assert scanner.file_processor_registry is FileProcessorRegistry

    def test_injected_registry_is_used(self, mock_config):
        """An explicitly passed registry is stored and used instead of the global."""
        snapshot = FileProcessorRegistry.snapshot()
        scanner = FileScanner(mock_config, file_processor_registry=snapshot)
        assert scanner.file_processor_registry is snapshot

    def test_empty_registry_finds_files_but_processes_none(self, mock_config, temp_dir):
        """With a registry that claims nothing, files are counted but not dispatched.

        This is the proof the injected registry is actually consulted: the same
        directory scanned with the default registry does process the file.
        """
        from pathlib import Path

        (Path(temp_dir) / "sample.txt").write_text("Contact: john.doe@example.com\n")

        empty = FileScanner(
            mock_config, file_processor_registry=_empty_processor_registry()
        )
        empty_result = empty.scan(temp_dir)

        default_result = FileScanner(mock_config).scan(temp_dir)

        # Discovery is registry-independent; dispatch is not.
        assert empty_result.total_files_found == default_result.total_files_found == 1
        assert empty_result.files_processed == 0
        assert default_result.files_processed == 1


class TestTextProcessorRegistryInjection:
    """``TextProcessor`` takes both registries and honours each independently."""

    def test_defaults_to_global_registries(self, mock_config):
        """Omitting both arguments keeps the pre-existing global behaviour."""
        processor = TextProcessor(mock_config, PiiMatchContainer())
        assert processor.file_processor_registry is FileProcessorRegistry
        assert processor.engine_registry is EngineRegistry

    def test_injected_registries_are_stored(self, mock_config):
        """Both registries are independently injectable."""
        processors = FileProcessorRegistry.snapshot()
        engines = EngineRegistry.snapshot()
        processor = TextProcessor(
            mock_config,
            PiiMatchContainer(),
            file_processor_registry=processors,
            engine_registry=engines,
        )
        assert processor.file_processor_registry is processors
        assert processor.engine_registry is engines

    def test_empty_engine_registry_loads_no_engines(self, tmp_path):
        """An empty engine registry yields a processor with zero engines.

        Uses a real regex-enabled ``Config`` (``mock_config`` disables every
        engine, which would make both sides trivially empty). The default
        registry loads the regex engine, so this distinguishes injection from a
        silently ignored argument.
        """
        config = _make_regex_config(
            str(tmp_path), logging.getLogger("test.registry_injection")
        )

        injected = TextProcessor(
            config, PiiMatchContainer(), engine_registry=_empty_engine_registry()
        )
        assert injected.engines == []

        default = TextProcessor(config, PiiMatchContainer())
        assert [e.name for e in default.engines] == ["regex"]

    def test_snapshot_engine_registry_still_loads_engines(self, tmp_path):
        """A populated snapshot behaves like the global registry it was taken from."""
        config = _make_regex_config(
            str(tmp_path), logging.getLogger("test.registry_injection")
        )
        processor = TextProcessor(
            config, PiiMatchContainer(), engine_registry=EngineRegistry.snapshot()
        )
        assert [e.name for e in processor.engines] == [
            e.name for e in TextProcessor(config, PiiMatchContainer()).engines
        ]


class TestScanRunnerRegistryInjection:
    """``ScanRequest`` threads both registries down into the pipeline."""

    def test_request_defaults_to_none(self, tmp_path):
        """Not specifying a registry leaves the fields ``None`` (global fallback)."""
        logger = logging.getLogger("test.registry_injection")
        request = ScanRequest(
            config=_make_regex_config(str(tmp_path), logger), logger=logger
        )
        assert request.file_processor_registry is None
        assert request.engine_registry is None

    def test_empty_processor_registry_reaches_the_scanner(self, tmp_path):
        """An empty processor registry on the request stops files being processed."""
        scan_dir = tmp_path / "data"
        scan_dir.mkdir()
        (scan_dir / "sample.txt").write_text(
            "Contact: john.doe@example.com IBAN DE89370400440532013000\n"
        )
        logger = logging.getLogger("test.registry_injection")

        result = ScanRunner().run(
            ScanRequest(
                config=_make_regex_config(str(scan_dir), logger),
                logger=logger,
                file_processor_registry=_empty_processor_registry(),
            )
        )

        assert result.total_files_found == 1
        assert result.files_processed == 0
        assert result.matches_found == 0

    def test_empty_engine_registry_reaches_the_processor(self, tmp_path):
        """An empty engine registry means the file is read but nothing detects PII."""
        scan_dir = tmp_path / "data"
        scan_dir.mkdir()
        (scan_dir / "sample.txt").write_text(
            "Contact: john.doe@example.com IBAN DE89370400440532013000\n"
        )
        logger = logging.getLogger("test.registry_injection")

        result = ScanRunner().run(
            ScanRequest(
                config=_make_regex_config(str(scan_dir), logger),
                logger=logger,
                engine_registry=_empty_engine_registry(),
            )
        )

        # The file is still dispatched to a processor -- only detection is empty.
        assert result.files_processed == 1
        assert result.matches_found == 0

    def test_default_registries_still_detect(self, tmp_path):
        """Control: the same scan without injection finds PII."""
        scan_dir = tmp_path / "data"
        scan_dir.mkdir()
        (scan_dir / "sample.txt").write_text(
            "Contact: john.doe@example.com IBAN DE89370400440532013000\n"
        )
        logger = logging.getLogger("test.registry_injection")

        result = ScanRunner().run(
            ScanRequest(config=_make_regex_config(str(scan_dir), logger), logger=logger)
        )

        assert result.files_processed == 1
        assert result.matches_found >= 1


class TestScannerServiceSnapshots:
    """``ScannerService`` pins one snapshot pair for its whole lifetime."""

    def _service(self, tmp_path):
        from analytics.store import AnalyticsStore
        from api.scanner_service import ScannerService

        store = AnalyticsStore(db_path=str(tmp_path / "analytics.db"))
        return ScannerService(store, allowed_scan_roots=[str(tmp_path)])

    def test_snapshots_are_populated(self, tmp_path):
        """Regression: the snapshots must not be empty.

        ``api/app.py`` imports neither ``file_processors`` nor ``core.engines``,
        so a snapshot taken without forcing those imports first would capture an
        empty registry and every API scan would silently process zero files.
        """
        service = self._service(tmp_path)
        try:
            assert service._file_processor_registry.get_all_processors()
            assert "regex" in service._engine_registry.list_engines()
        finally:
            service.shutdown()

    def test_snapshots_are_isolated_from_later_registration(self, tmp_path):
        """A processor registered after construction must not leak into the snapshot."""
        service = self._service(tmp_path)
        try:
            before = len(service._file_processor_registry.get_all_processors())

            class _FakeProcessor:
                def can_process(self, extension, file_path="", mime_type=""):
                    return extension == ".neverseen"

                def extract_text(self, file_path):  # pragma: no cover - not called
                    return ""

            with FileProcessorRegistry.isolated():
                FileProcessorRegistry.register(_FakeProcessor())
                assert (
                    len(service._file_processor_registry.get_all_processors()) == before
                )
                assert (
                    service._file_processor_registry.get_processor(".neverseen") is None
                )
        finally:
            service.shutdown()

    def test_engine_snapshot_isolated_from_later_registration(self, tmp_path):
        """An engine registered after construction must not leak into the snapshot."""
        service = self._service(tmp_path)
        try:
            with EngineRegistry.isolated():
                EngineRegistry.register("never-seen", _StubEngine)
                assert "never-seen" not in service._engine_registry.list_engines()
                assert EngineRegistry.is_registered("never-seen")
        finally:
            service.shutdown()


class _StubEngine(DetectionEngine):
    """Minimal engine used only to prove snapshot isolation."""

    name = "never-seen"

    def __init__(self, config):
        self.config = config

    def is_available(self) -> bool:
        return True

    def detect(self, text, file_path="", **kwargs):  # pragma: no cover - not called
        return []


class TestRegistryInterchangeability:
    """The class object and a snapshot expose the same lookup surface."""

    def test_processor_registry_surfaces_match(self):
        """``FileProcessorRegistry`` and its snapshot answer the same questions."""
        snapshot = FileProcessorRegistry.snapshot()
        assert snapshot.get_supported_extensions() == (
            FileProcessorRegistry.get_supported_extensions()
        )
        assert len(snapshot.get_all_processors()) == len(
            FileProcessorRegistry.get_all_processors()
        )
        assert (snapshot.get_processor(".txt") is None) == (
            FileProcessorRegistry.get_processor(".txt") is None
        )

    def test_engine_registry_surfaces_match(self):
        """``EngineRegistry`` and its snapshot answer the same questions."""
        snapshot = EngineRegistry.snapshot()
        assert sorted(snapshot.list_engines()) == sorted(EngineRegistry.list_engines())
        assert snapshot.is_registered("regex") == EngineRegistry.is_registered("regex")
