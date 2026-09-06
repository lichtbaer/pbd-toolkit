"""Unit tests for ``core.engines.vector_engine.VectorEngine``.

``sentence-transformers`` is not installed in the test environment and must
not be.  Two strategies are used:

* Most behavioural tests replace ``engine._indexer`` with a ``StubIndexer``
  that returns scripted ``CategoryMatch`` objects (or raises), so the engine's
  own logic – enable flag, error handling, chunk bookkeeping, thread-local
  file context, triage, finalisation – is tested in isolation.
* A handful of end-to-end tests run the real ``DocumentIndexer`` against a
  fake ``sentence_transformers`` module injected into ``sys.modules`` with
  ``monkeypatch`` (removed again after each test).  The fake model returns
  deterministic vectors: every built-in exemplar maps onto its category's
  unit axis, and query texts are registered with a chosen cosine similarity.

``VectorEngine.set_current_file`` itself is already covered in
``tests/test_vector_features.py``; here it is exercised through ``detect``.
"""

from __future__ import annotations

import hashlib
import logging
import math
import sys
import threading
import types
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest

from core.config import Config
from core.engines.base import DetectionResult
from core.engines.vector_engine import VectorEngine
from core.indexer.document_indexer import CategoryMatch, DocumentIndexer
from core.indexer.pii_queries import PII_EXEMPLARS

MODEL = "fake/engine-test-model"

# ---------------------------------------------------------------------------
# Deterministic fake sentence-transformers (see module docstring)
# ---------------------------------------------------------------------------

CATEGORIES: list[str] = list(PII_EXEMPLARS)
N_CAT = len(CATEGORIES)
NOISE_AXIS = N_CAT
TILT_AXIS = N_CAT + 1
SPARE_AXIS = N_CAT + 2
DIM = N_CAT + 3

_EXEMPLAR_POS: dict[str, tuple[int, int]] = {
    text: (CATEGORIES.index(category), i)
    for category, texts in PII_EXEMPLARS.items()
    for i, text in enumerate(texts)
}


def pii_vector(category: str, strength: float = 1.0) -> np.ndarray:
    v = np.zeros(DIM, dtype=np.float32)
    v[CATEGORIES.index(category)] = strength
    v[NOISE_AXIS] = math.sqrt(max(0.0, 1.0 - strength * strength))
    return v


def _default_vector(text: str) -> np.ndarray:
    v = np.zeros(DIM, dtype=np.float32)
    pos = _EXEMPLAR_POS.get(text)
    if pos is not None:
        cat_idx, i = pos
        v[cat_idx] = 1.0
        v[TILT_AXIS] = 0.1 * i
    else:
        theta = hashlib.sha256(text.encode()).digest()[0] / 255.0 * (math.pi / 2)
        v[NOISE_AXIS] = math.cos(theta)
        v[SPARE_AXIS] = math.sin(theta)
    return v


class FakeSentenceTransformer:
    vectors: dict[str, np.ndarray] = {}

    def __init__(self, model_name: str, **kwargs) -> None:
        self.model_name = model_name

    def encode(self, texts, **kwargs):
        return np.stack(
            [FakeSentenceTransformer.vectors.get(t, _default_vector(t)) for t in texts]
        )


@pytest.fixture
def fake_st(monkeypatch, tmp_path):
    module = types.ModuleType("sentence_transformers")
    module.SentenceTransformer = FakeSentenceTransformer
    monkeypatch.setitem(sys.modules, "sentence_transformers", module)
    monkeypatch.setattr(FakeSentenceTransformer, "vectors", {})
    monkeypatch.setattr(DocumentIndexer, "_model_cache", {})
    monkeypatch.setenv("HOME", str(tmp_path / "home"))  # exemplar cache location
    return FakeSentenceTransformer


@pytest.fixture
def no_st(monkeypatch):
    monkeypatch.setitem(sys.modules, "sentence_transformers", None)


# ---------------------------------------------------------------------------
# Scripted indexer stub
# ---------------------------------------------------------------------------


class StubIndexer:
    """Minimal stand-in for DocumentIndexer used by most engine tests."""

    def __init__(self, matches=None, error: Exception | None = None) -> None:
        self.matches = list(matches or [])
        self.error = error
        self.model_name = MODEL
        self.threshold = 0.75
        self.detect_calls: list[str] = []
        self.add_calls: list[dict] = []
        self.save_calls = 0
        self.add_error: Exception | None = None
        self.save_error: Exception | None = None
        self.available = True

    def detect(self, text):
        self.detect_calls.append(text)
        if self.error is not None:
            raise self.error
        return list(self.matches)

    def add_chunk(self, text, file_path, chunk_idx=0, file_hash=""):
        if self.add_error is not None:
            raise self.add_error
        self.add_calls.append(
            {
                "text": text,
                "file_path": file_path,
                "chunk_idx": chunk_idx,
                "file_hash": file_hash,
                "thread": threading.current_thread().name,
            }
        )

    def save_index(self):
        self.save_calls += 1
        if self.save_error is not None:
            raise self.save_error

    def is_available(self):
        return self.available


def _config(**overrides) -> SimpleNamespace:
    values = {
        "use_vector_search": True,
        "use_vector_triage": False,
        "vector_threshold": 0.75,
        "vector_model": MODEL,
        "vector_save_index": None,
        "vector_load_index": None,
        "vector_custom_exemplars": None,
        "vector_index_store_text": True,
        "verbose": False,
        "logger": Mock(),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _engine(stub: StubIndexer | None = None, **overrides) -> VectorEngine:
    engine = VectorEngine(_config(**overrides))
    if stub is not None:
        engine._indexer = stub
    return engine


def _match(category="VECTOR_EMAIL", score=0.9123456, exemplar="ex") -> CategoryMatch:
    return CategoryMatch(category=category, score=score, best_exemplar=exemplar)


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestConstruction:
    def test_class_attributes(self):
        assert VectorEngine.name == "vector-search"
        assert VectorEngine.thread_safe is True

    def test_from_real_config(self, tmp_path):
        cfg = Config(
            use_vector_search=True,
            use_vector_triage=True,
            vector_threshold=0.6,
            vector_model="my/model",
            vector_save_index=str(tmp_path / "save"),
            vector_load_index=str(tmp_path / "load"),
            vector_custom_exemplars=str(tmp_path / "custom.json"),
            vector_index_store_text=False,
            verbose=True,
            logger=Mock(),
        )
        engine = VectorEngine(cfg)

        assert engine.config is cfg
        assert engine.enabled is True
        assert engine.triage_mode is True
        assert isinstance(engine._indexer, DocumentIndexer)
        indexer = engine._indexer
        assert indexer.model_name == "my/model"
        assert indexer.threshold == 0.6
        assert indexer.save_index_path == str(tmp_path / "save")
        assert indexer.load_index_path == str(tmp_path / "load")
        assert indexer.custom_exemplars_path == str(tmp_path / "custom.json")
        assert indexer.verbose is True
        assert indexer.store_text is False
        assert indexer._initialized is False  # nothing loaded eagerly
        assert engine._chunk_counter == 0
        assert engine._available is None

    def test_defaults_from_real_config(self):
        engine = VectorEngine(Config())
        assert engine.enabled is False
        assert engine.triage_mode is False
        assert engine._indexer.model_name == "sentence-transformers/all-MiniLM-L6-v2"
        assert engine._indexer.threshold == 0.75
        assert engine._indexer.save_index_path is None
        assert engine._indexer.load_index_path is None
        assert engine._indexer.custom_exemplars_path is None
        assert engine._indexer.store_text is True

    def test_from_minimal_namespace_uses_defaults(self):
        engine = VectorEngine(SimpleNamespace(use_vector_search=True))
        assert engine.enabled is True
        assert engine.triage_mode is False
        assert engine._indexer.model_name == "sentence-transformers/all-MiniLM-L6-v2"
        assert engine._indexer.threshold == 0.75
        assert engine._indexer.verbose is False
        assert engine._indexer.store_text is True

    def test_empty_string_paths_become_none(self):
        engine = _engine(
            vector_save_index="", vector_load_index="", vector_custom_exemplars=""
        )
        assert engine._indexer.save_index_path is None
        assert engine._indexer.load_index_path is None
        assert engine._indexer.custom_exemplars_path is None

    def test_flags_are_coerced_to_bool(self):
        engine = _engine(
            use_vector_search=1, use_vector_triage="yes", vector_threshold="0.5"
        )
        assert engine.enabled is True
        assert engine.triage_mode is True
        assert engine._indexer.threshold == 0.5


# ---------------------------------------------------------------------------
# is_available
# ---------------------------------------------------------------------------


class TestAvailability:
    def test_disabled_engine_is_never_available(self, fake_st):
        stub = StubIndexer()
        engine = _engine(stub, use_vector_search=False)
        assert engine.is_available() is False
        assert engine._available is None  # indexer not even consulted

    def test_unavailable_when_sentence_transformers_missing(self, no_st):
        engine = _engine()
        assert engine.is_available() is False
        assert engine._available is False
        engine.config.logger.warning.assert_not_called()  # not verbose

    def test_missing_dependency_warns_once_when_verbose(self, no_st):
        engine = _engine(verbose=True)
        assert engine.is_available() is False
        assert engine.is_available() is False
        engine.config.logger.warning.assert_called_once()
        message = engine.config.logger.warning.call_args.args[0]
        assert "sentence-transformers is not installed" in message
        assert "pip install sentence-transformers" in message

    def test_available_when_dependency_present(self, fake_st):
        engine = _engine(verbose=True)
        assert engine.is_available() is True
        assert engine._available is True
        engine.config.logger.warning.assert_not_called()

    def test_result_is_cached_on_engine(self, fake_st):
        stub = StubIndexer()
        engine = _engine(stub)
        assert engine.is_available() is True
        stub.available = False
        assert engine.is_available() is True


# ---------------------------------------------------------------------------
# detect() with a scripted indexer
# ---------------------------------------------------------------------------


class TestDetectWithStub:
    def test_disabled_engine_returns_empty_without_touching_indexer(self):
        stub = StubIndexer(matches=[_match()])
        engine = _engine(stub, use_vector_search=False)
        assert engine.detect("Kontakt: max@example.de") == []
        assert stub.detect_calls == []

    @pytest.mark.parametrize("text", ["", "   ", "\n\t"])
    def test_blank_text_returns_empty(self, text):
        stub = StubIndexer(matches=[_match()])
        engine = _engine(stub)
        assert engine.detect(text) == []
        assert stub.detect_calls == []

    def test_no_matches_returns_empty_and_indexes_nothing(self, tmp_path):
        stub = StubIndexer(matches=[])
        engine = _engine(stub, vector_save_index=str(tmp_path / "idx"))
        assert engine.detect("plain text") == []
        assert stub.detect_calls == ["plain text"]
        assert stub.add_calls == []
        assert engine._chunk_counter == 0

    def test_matches_become_detection_results(self):
        stub = StubIndexer(
            matches=[
                _match(
                    "VECTOR_EMAIL", 0.9123456, "E-Mail-Adresse: info@unternehmen.com"
                ),
                _match("VECTOR_PHONE", 0.77777, "Phone: +1 (555) 234-5678"),
            ]
        )
        engine = _engine(stub)
        text = "Mail info@unternehmen.com, Tel +1 555 234 5678"

        results = engine.detect(text, labels=["ignored"])

        assert len(results) == 2
        assert all(isinstance(r, DetectionResult) for r in results)
        first, second = results
        assert first.text == text
        assert first.entity_type == "VECTOR_EMAIL"
        assert first.confidence == 0.9123
        assert first.engine_name == "vector-search"
        assert first.offset is None  # whole-chunk match, no sub-span offset
        assert first.metadata == {
            "similarity": 0.9123,
            "best_exemplar": "E-Mail-Adresse: info@unternehmen.com",
            "model": MODEL,
            "threshold": 0.75,
        }
        assert second.entity_type == "VECTOR_PHONE"
        assert second.confidence == 0.7778
        assert second.metadata["similarity"] == 0.7778
        assert second.text == text

    def test_indexer_error_is_logged_and_swallowed(self):
        stub = StubIndexer(error=RuntimeError("model exploded"))
        engine = _engine(stub)
        assert engine.detect("some text") == []
        logger = engine.config.logger
        logger.warning.assert_called_once()
        assert "model exploded" in logger.warning.call_args.args[0]
        assert "[vector] Detection failed" in logger.warning.call_args.args[0]
        logger.debug.assert_not_called()

    def test_indexer_error_adds_traceback_when_verbose(self):
        stub = StubIndexer(error=ValueError("bad input"))
        engine = _engine(stub, verbose=True)
        assert engine.detect("some text") == []
        logger = engine.config.logger
        logger.warning.assert_called_once()
        logger.debug.assert_called_once()
        assert logger.debug.call_args.kwargs.get("exc_info") is True


class TestChunkIndexing:
    def test_no_indexing_without_save_path(self):
        stub = StubIndexer(matches=[_match()])
        engine = _engine(stub, vector_save_index=None)
        engine.set_current_file("/data/a.txt", "hash-a")
        assert len(engine.detect("text")) == 1
        assert stub.add_calls == []
        assert engine._chunk_counter == 0

    def test_matching_chunks_are_indexed_with_file_context(self, tmp_path):
        stub = StubIndexer(matches=[_match()])
        engine = _engine(stub, vector_save_index=str(tmp_path / "idx"))
        engine.set_current_file("/data/a.txt", "hash-a")

        engine.detect("first chunk")
        engine.detect("second chunk")
        engine.set_current_file("/data/b.txt")
        engine.detect("third chunk")

        assert [
            (c["text"], c["file_path"], c["chunk_idx"], c["file_hash"])
            for c in stub.add_calls
        ] == [
            ("first chunk", "/data/a.txt", 0, "hash-a"),
            ("second chunk", "/data/a.txt", 1, "hash-a"),
            ("third chunk", "/data/b.txt", 2, ""),
        ]
        assert engine._chunk_counter == 3

    def test_default_context_when_no_file_was_set(self, tmp_path):
        stub = StubIndexer(matches=[_match()])
        engine = _engine(stub, vector_save_index=str(tmp_path / "idx"))
        engine.detect("orphan chunk")
        assert stub.add_calls == [
            {
                "text": "orphan chunk",
                "file_path": "<scan>",
                "chunk_idx": 0,
                "file_hash": "",
                "thread": threading.current_thread().name,
            }
        ]

    def test_file_context_is_thread_local(self, tmp_path):
        stub = StubIndexer(matches=[_match()])
        engine = _engine(stub, vector_save_index=str(tmp_path / "idx"))
        engine.set_current_file("/main.txt", "hash-main")
        barrier = threading.Barrier(2)

        def worker(path: str, digest: str) -> None:
            engine.set_current_file(path, digest)
            barrier.wait()  # both threads have set their context before detecting
            engine.detect(f"chunk of {path}")

        threads = [
            threading.Thread(target=worker, args=("/t1.txt", "h1"), name="w1"),
            threading.Thread(target=worker, args=("/t2.txt", "h2"), name="w2"),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        engine.detect("chunk of main")

        by_thread = {c["thread"]: c for c in stub.add_calls}
        assert by_thread["w1"]["file_path"] == "/t1.txt"
        assert by_thread["w1"]["file_hash"] == "h1"
        assert by_thread["w2"]["file_path"] == "/t2.txt"
        assert by_thread["w2"]["file_hash"] == "h2"
        main = by_thread[threading.current_thread().name]
        assert (main["file_path"], main["file_hash"]) == ("/main.txt", "hash-main")
        assert sorted(c["chunk_idx"] for c in stub.add_calls) == [0, 1, 2]

    def test_add_chunk_failure_does_not_affect_results(self, tmp_path):
        stub = StubIndexer(matches=[_match()])
        stub.add_error = RuntimeError("index full")
        engine = _engine(stub, vector_save_index=str(tmp_path / "idx"))
        results = engine.detect("text")
        assert [r.entity_type for r in results] == ["VECTOR_EMAIL"]
        engine.config.logger.debug.assert_not_called()  # silent when not verbose
        engine.config.logger.warning.assert_not_called()
        assert engine._chunk_counter == 1  # counter still consumed

    def test_add_chunk_failure_logged_when_verbose(self, tmp_path):
        stub = StubIndexer(matches=[_match()])
        stub.add_error = RuntimeError("index full")
        engine = _engine(stub, vector_save_index=str(tmp_path / "idx"), verbose=True)
        assert len(engine.detect("text")) == 1
        logger = engine.config.logger
        logger.debug.assert_called_once()
        assert "Chunk indexing failed" in logger.debug.call_args.args[0]
        assert logger.debug.call_args.args[1] is stub.add_error
        assert logger.debug.call_args.kwargs.get("exc_info") is True


# ---------------------------------------------------------------------------
# triage_pass
# ---------------------------------------------------------------------------


class TestTriagePass:
    @pytest.mark.parametrize("text", ["", "  \n"])
    def test_blank_text_fails_triage(self, text):
        stub = StubIndexer(matches=[_match()])
        engine = _engine(stub, use_vector_triage=True)
        assert engine.triage_pass(text) is False
        assert stub.detect_calls == []

    def test_signal_passes_triage(self):
        stub = StubIndexer(matches=[_match()])
        engine = _engine(stub, use_vector_triage=True)
        assert engine.triage_pass("IBAN DE89 ...") is True
        assert stub.detect_calls == ["IBAN DE89 ..."]

    def test_no_signal_fails_triage(self):
        engine = _engine(StubIndexer(matches=[]), use_vector_triage=True)
        assert engine.triage_pass("nothing here") is False

    def test_error_is_conservative_and_passes(self):
        engine = _engine(
            StubIndexer(error=RuntimeError("boom")), use_vector_triage=True
        )
        assert engine.triage_pass("anything") is True
        engine.config.logger.warning.assert_not_called()

    def test_triage_does_not_index_chunks(self, tmp_path):
        stub = StubIndexer(matches=[_match()])
        engine = _engine(stub, use_vector_triage=True, vector_save_index=str(tmp_path))
        assert engine.triage_pass("text") is True
        assert stub.add_calls == []

    def test_triage_ignores_enabled_flag(self):
        """Current behaviour: triage_pass does not check ``enabled``; the
        caller (TextProcessor) is responsible for only using it when the
        engine is active."""
        stub = StubIndexer(matches=[_match()])
        engine = _engine(stub, use_vector_search=False, use_vector_triage=True)
        assert engine.triage_pass("text") is True


# ---------------------------------------------------------------------------
# finalize
# ---------------------------------------------------------------------------


class TestFinalize:
    def test_noop_without_save_path(self):
        stub = StubIndexer()
        engine = _engine(stub, vector_save_index=None)
        engine.finalize()
        assert stub.save_calls == 0

    def test_saves_index_when_configured(self, tmp_path):
        stub = StubIndexer()
        engine = _engine(stub, vector_save_index=str(tmp_path / "idx"))
        engine.finalize()
        assert stub.save_calls == 1
        engine.config.logger.warning.assert_not_called()

    def test_save_failure_is_logged(self, tmp_path):
        stub = StubIndexer()
        stub.save_error = OSError("read-only file system")
        engine = _engine(stub, vector_save_index=str(tmp_path / "idx"))
        engine.finalize()  # must not raise
        logger = engine.config.logger
        logger.warning.assert_called_once()
        message = logger.warning.call_args.args[0]
        assert "[vector] Failed to save index" in message
        assert "read-only file system" in message


# ---------------------------------------------------------------------------
# End-to-end with the real DocumentIndexer and the fake model
# ---------------------------------------------------------------------------


class TestEndToEnd:
    def test_detect_reports_categories_above_threshold(self, fake_st):
        text = "Kontakt: erika.muster@example.de, Tel. +49 151 1234567"
        v = np.zeros(DIM, dtype=np.float32)
        v[CATEGORIES.index("VECTOR_EMAIL")] = 0.8
        v[CATEGORIES.index("VECTOR_PHONE")] = 0.6
        fake_st.vectors[text] = v
        engine = _engine(vector_threshold=0.5)

        results = engine.detect(text)

        assert [(r.entity_type, r.confidence) for r in results] == [
            ("VECTOR_EMAIL", 0.8),
            ("VECTOR_PHONE", 0.6),
        ]
        for r in results:
            assert r.text == text
            assert r.engine_name == "vector-search"
            assert r.offset is None
            assert r.metadata["model"] == MODEL
            assert r.metadata["threshold"] == 0.5
        assert results[0].metadata["best_exemplar"] == PII_EXEMPLARS["VECTOR_EMAIL"][0]
        assert results[1].metadata["best_exemplar"] == PII_EXEMPLARS["VECTOR_PHONE"][0]

    def test_threshold_from_config_filters_matches(self, fake_st):
        fake_st.vectors["weak"] = pii_vector("VECTOR_SSN", 0.7)
        assert _engine(vector_threshold=0.75).detect("weak") == []
        hits = _engine(vector_threshold=0.65).detect("weak")
        assert [r.entity_type for r in hits] == ["VECTOR_SSN"]
        assert hits[0].confidence == pytest.approx(0.7, abs=1e-4)

    def test_unrelated_text_has_no_findings(self, fake_st):
        engine = _engine(vector_threshold=0.2)
        assert engine.detect("Die Sitzung beginnt um neun Uhr.") == []
        assert engine.triage_pass("Die Sitzung beginnt um neun Uhr.") is False

    def test_triage_and_detect_agree(self, fake_st):
        fake_st.vectors["card"] = pii_vector("VECTOR_CREDITCARD", 0.95)
        engine = _engine(use_vector_triage=True)
        assert engine.triage_pass("card") is True
        assert [r.entity_type for r in engine.detect("card")] == ["VECTOR_CREDITCARD"]

    def test_detect_indexes_chunks_into_real_indexer(self, fake_st, tmp_path):
        fake_st.vectors["hit"] = pii_vector("VECTOR_HEALTH", 0.9)
        engine = _engine(vector_save_index=str(tmp_path / "idx"))
        engine.set_current_file("/scan/a.txt", "deadbeef")
        engine.detect("hit")
        engine.detect("miss")  # no match -> not indexed
        engine.detect("hit")

        indexer = engine._indexer
        assert indexer.num_indexed_chunks == 2
        assert [(c.file_path, c.chunk_idx, c.file_hash) for c in indexer._chunks] == [
            ("/scan/a.txt", 0, "deadbeef"),
            ("/scan/a.txt", 1, "deadbeef"),
        ]
        assert indexer.get_indexed_file_hashes() == {"/scan/a.txt": "deadbeef"}
        similar = indexer.query_similar_chunks("hit", top_k=5, threshold=0.99)
        assert len(similar) == 2

    def test_finalize_without_faiss_logs_via_indexer(
        self, fake_st, monkeypatch, caplog
    ):
        caplog.set_level(logging.WARNING, logger="core.indexer.document_indexer")
        monkeypatch.setitem(sys.modules, "faiss", None)
        fake_st.vectors["hit"] = pii_vector("VECTOR_PERSON", 0.9)
        engine = _engine(vector_save_index="/nonexistent/dir/idx")
        engine.detect("hit")
        engine.finalize()
        # The indexer swallows the ImportError itself; the engine sees no error.
        engine.config.logger.warning.assert_not_called()
        assert any(
            "faiss-cpu not installed" in r.getMessage()
            for r in caplog.records
            if r.name == "core.indexer.document_indexer"
        )

    def test_model_load_failure_surfaces_as_warning(self, fake_st, monkeypatch):
        def broken(model_name, **kwargs):
            raise OSError("no cached model and network disabled")

        monkeypatch.setattr(
            sys.modules["sentence_transformers"], "SentenceTransformer", broken
        )
        engine = _engine()
        assert engine.is_available() is True  # module importable ...
        assert engine.detect("anything") == []  # ... but loading fails gracefully
        message = engine.config.logger.warning.call_args.args[0]
        assert "Failed to load embedding model" in message
        assert MODEL in message
