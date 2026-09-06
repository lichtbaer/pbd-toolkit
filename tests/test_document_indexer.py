"""Unit tests for ``core.indexer.document_indexer.DocumentIndexer``.

``sentence-transformers`` and ``faiss`` are *not* installed in the test
environment and must not be.  Both are replaced by small fake modules that are
injected into ``sys.modules`` via ``monkeypatch`` (and therefore removed again
after each test):

* ``FakeSentenceTransformer.encode`` returns deterministic vectors.  Every
  built-in exemplar text maps onto the unit axis of its PII category (with a
  small, index-dependent tilt so that the first exemplar of a category is
  always the best match and normalisation is exercised).  Query texts are
  registered explicitly with :func:`pii_vector`, whose cosine similarity to a
  category is exactly the requested ``strength``.  Unknown texts map onto a
  hash-derived unit vector that is orthogonal to every exemplar.
* ``FakeIndexFlatIP`` is an in-memory inner-product index with ``add``,
  ``search``, ``reconstruct`` and ``ntotal``; ``write_index``/``read_index``
  round-trip it through a ``.npy`` file.

Custom exemplar *loading*, file-hash bookkeeping and the basic brute-force
vs. FAISS dispatch are already covered in ``tests/test_vector_features.py``
and are not repeated here.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import sys
import threading
import types

import numpy as np
import pytest

from core.indexer.document_indexer import (
    CategoryMatch,
    DocumentIndexer,
    IndexedChunk,
)
from core.indexer.pii_queries import EXEMPLAR_PAIRS, PII_EXEMPLARS

LOGGER_NAME = "core.indexer.document_indexer"
MODEL = "fake/test-model"

# ---------------------------------------------------------------------------
# Deterministic embedding space
# ---------------------------------------------------------------------------

CATEGORIES: list[str] = list(PII_EXEMPLARS)
N_CAT = len(CATEGORIES)
NOISE_AXIS = N_CAT  # remainder of a query vector / unknown texts
TILT_AXIS = N_CAT + 1  # small perturbation for exemplar index > 0
SPARE_AXIS = N_CAT + 2  # second axis of the "unknown text" plane
DIM = N_CAT + 3

_EXEMPLAR_POS: dict[str, tuple[int, int]] = {
    text: (CATEGORIES.index(category), i)
    for category, texts in PII_EXEMPLARS.items()
    for i, text in enumerate(texts)
}


def pii_vector(category: str, strength: float = 1.0) -> np.ndarray:
    """Unit vector whose cosine similarity to *category*'s best exemplar is *strength*."""
    v = np.zeros(DIM, dtype=np.float32)
    v[CATEGORIES.index(category)] = strength
    v[NOISE_AXIS] = math.sqrt(max(0.0, 1.0 - strength * strength))
    return v


def axis_vector(axis: int) -> np.ndarray:
    v = np.zeros(DIM, dtype=np.float32)
    v[axis] = 1.0
    return v


def _default_vector(text: str) -> np.ndarray:
    v = np.zeros(DIM, dtype=np.float32)
    pos = _EXEMPLAR_POS.get(text)
    if pos is not None:
        cat_idx, i = pos
        v[cat_idx] = 1.0
        v[TILT_AXIS] = 0.1 * i  # un-normalised on purpose
    else:
        theta = hashlib.sha256(text.encode()).digest()[0] / 255.0 * (math.pi / 2)
        v[NOISE_AXIS] = math.cos(theta)
        v[SPARE_AXIS] = math.sin(theta)
    return v


class FakeSentenceTransformer:
    """Stand-in for ``sentence_transformers.SentenceTransformer``."""

    vectors: dict[str, np.ndarray] = {}
    instances: list[FakeSentenceTransformer] = []
    fail_init: Exception | None = None

    def __init__(self, model_name: str, **kwargs) -> None:
        if FakeSentenceTransformer.fail_init is not None:
            raise FakeSentenceTransformer.fail_init
        self.model_name = model_name
        self.calls: list[list[str]] = []
        self.last_kwargs: dict = {}
        FakeSentenceTransformer.instances.append(self)

    def encode(self, texts, **kwargs):
        self.calls.append(list(texts))
        self.last_kwargs = kwargs
        return np.stack(
            [FakeSentenceTransformer.vectors.get(t, _default_vector(t)) for t in texts]
        )


# ---------------------------------------------------------------------------
# Fake faiss
# ---------------------------------------------------------------------------


class FakeIndexFlatIP:
    def __init__(self, d: int) -> None:
        self.d = d
        self._vectors = np.zeros((0, d), dtype=np.float32)

    @property
    def ntotal(self) -> int:
        return len(self._vectors)

    def add(self, x) -> None:
        x = np.asarray(x, dtype=np.float32).reshape(-1, self.d)
        self._vectors = np.vstack([self._vectors, x])

    def search(self, q, k: int):
        sims = self._vectors @ np.asarray(q, dtype=np.float32).reshape(-1)
        order = np.argsort(-sims, kind="stable")[:k]
        return sims[order].reshape(1, -1), order.astype(np.int64).reshape(1, -1)

    def reconstruct(self, i: int) -> np.ndarray:
        return self._vectors[i].copy()


def _fake_write_index(index: FakeIndexFlatIP, path: str) -> None:
    with open(path, "wb") as fh:
        np.save(fh, index._vectors)


def _fake_read_index(path: str) -> FakeIndexFlatIP:
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    with open(path, "rb") as fh:
        vectors = np.load(fh)
    index = FakeIndexFlatIP(vectors.shape[1])
    index.add(vectors)
    return index


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_st(monkeypatch, tmp_path):
    """Install the fake sentence-transformers module for one test."""
    module = types.ModuleType("sentence_transformers")
    module.SentenceTransformer = FakeSentenceTransformer
    monkeypatch.setitem(sys.modules, "sentence_transformers", module)
    monkeypatch.setattr(FakeSentenceTransformer, "vectors", {})
    monkeypatch.setattr(FakeSentenceTransformer, "instances", [])
    monkeypatch.setattr(FakeSentenceTransformer, "fail_init", None)
    monkeypatch.setattr(DocumentIndexer, "_model_cache", {})
    # Exemplar embedding cache lives under ~/.cache – keep it inside tmp_path.
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    return FakeSentenceTransformer


@pytest.fixture
def fake_faiss(monkeypatch):
    module = types.ModuleType("faiss")
    module.IndexFlatIP = FakeIndexFlatIP
    module.write_index = _fake_write_index
    module.read_index = _fake_read_index
    monkeypatch.setitem(sys.modules, "faiss", module)
    return module


@pytest.fixture
def no_faiss(monkeypatch):
    monkeypatch.setitem(sys.modules, "faiss", None)


def _indexer(**kwargs) -> DocumentIndexer:
    kwargs.setdefault("model_name", MODEL)
    return DocumentIndexer(**kwargs)


def _records(caplog, level=None):
    return [
        r
        for r in caplog.records
        if r.name == LOGGER_NAME and (level is None or r.levelno == level)
    ]


# ---------------------------------------------------------------------------
# Availability
# ---------------------------------------------------------------------------


class TestAvailability:
    def test_unavailable_when_sentence_transformers_missing(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "sentence_transformers", None)
        indexer = _indexer()
        assert indexer.is_available() is False

    def test_result_is_cached(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "sentence_transformers", None)
        indexer = _indexer()
        assert indexer.is_available() is False
        # Installing the package afterwards does not change the cached answer.
        monkeypatch.setitem(
            sys.modules, "sentence_transformers", types.ModuleType("st")
        )
        assert indexer.is_available() is False
        assert indexer._available is False

    def test_available_with_fake_module(self, fake_st):
        indexer = _indexer()
        assert indexer.is_available() is True
        assert indexer._available is True


# ---------------------------------------------------------------------------
# Initialisation, model loading, exemplar precomputation
# ---------------------------------------------------------------------------


class TestInitialisation:
    def test_constructor_does_not_load_model(self, fake_st):
        indexer = _indexer(threshold=0.6)
        assert indexer._initialized is False
        assert indexer._model is None
        assert indexer._exemplar_embeddings is None
        assert fake_st.instances == []
        assert indexer.threshold == 0.6
        assert indexer.model_name == MODEL

    def test_ensure_initialized_loads_model_and_exemplars(self, fake_st):
        indexer = _indexer()
        indexer._ensure_initialized()

        assert indexer._initialized is True
        assert len(fake_st.instances) == 1
        model = fake_st.instances[0]
        assert model.model_name == MODEL
        assert indexer._model is model
        assert DocumentIndexer._model_cache[MODEL] is model

        # All exemplars are embedded in one batch with the documented kwargs.
        assert model.calls == [[text for _, text in EXEMPLAR_PAIRS]]
        assert model.last_kwargs == {
            "show_progress_bar": False,
            "convert_to_numpy": True,
            "normalize_embeddings": False,
        }

        matrix = indexer._exemplar_embeddings
        assert matrix.shape == (len(EXEMPLAR_PAIRS), DIM)
        assert matrix.dtype == np.float32
        # Rows are L2-normalised even though the fake model returned tilted,
        # un-normalised vectors for exemplar index > 0.
        np.testing.assert_allclose(np.linalg.norm(matrix, axis=1), 1.0, atol=1e-6)
        assert indexer._exemplar_categories == [c for c, _ in EXEMPLAR_PAIRS]
        assert indexer._exemplar_texts == [t for _, t in EXEMPLAR_PAIRS]

    def test_ensure_initialized_is_idempotent(self, fake_st):
        indexer = _indexer()
        indexer._ensure_initialized()
        indexer._ensure_initialized()
        assert len(fake_st.instances) == 1
        assert len(fake_st.instances[0].calls) == 1

    def test_concurrent_initialisation_loads_model_once(self, fake_st, monkeypatch):
        """Second thread blocks on the lock and takes the double-checked early
        return once the first thread has finished initialising."""
        started = threading.Event()
        release = threading.Event()

        class SlowTransformer(FakeSentenceTransformer):
            def __init__(self, model_name, **kwargs):
                started.set()
                assert release.wait(timeout=5)
                super().__init__(model_name, **kwargs)

        monkeypatch.setattr(
            sys.modules["sentence_transformers"], "SentenceTransformer", SlowTransformer
        )
        indexer = _indexer()
        first = threading.Thread(target=indexer._ensure_initialized)
        first.start()
        assert started.wait(timeout=5)  # first thread now holds _embed_lock
        second = threading.Thread(target=indexer._ensure_initialized)
        second.start()
        release.set()
        first.join(timeout=5)
        second.join(timeout=5)

        assert indexer._initialized is True
        assert len(fake_st.instances) == 1
        assert len(fake_st.instances[0].calls) == 1

    def test_model_shared_between_instances_and_exemplar_cache_reused(
        self, fake_st, tmp_path
    ):
        first = _indexer()
        first._ensure_initialized()
        cache_dir = tmp_path / "home" / ".cache" / "pbd-toolkit"
        cache_files = list(cache_dir.glob("exemplar_embeddings_fake_test-model_*.npz"))
        assert len(cache_files) == 1

        second = _indexer()
        second._ensure_initialized()
        # Same model object, no second construction, no second encode() call
        # because the exemplar matrix came from the on-disk cache.
        assert second._model is first._model
        assert len(fake_st.instances) == 1
        assert len(fake_st.instances[0].calls) == 1
        np.testing.assert_array_equal(
            second._exemplar_embeddings, first._exemplar_embeddings
        )
        assert second._exemplar_categories == first._exemplar_categories

    def test_verbose_logging_during_initialisation(self, fake_st, caplog):
        caplog.set_level(logging.DEBUG, logger=LOGGER_NAME)
        _indexer(verbose=True)._ensure_initialized()
        messages = [r.getMessage() for r in _records(caplog)]
        assert any("Loading embedding model" in m for m in messages)
        assert any("Model loaded" in m for m in messages)
        assert any("Pre-computing" in m for m in messages)
        assert any("Exemplar matrix ready" in m for m in messages)
        assert any("cached to" in m for m in messages)

        caplog.clear()
        _indexer(verbose=True)._ensure_initialized()
        messages = [r.getMessage() for r in _records(caplog)]
        assert any("Loaded cached exemplar embeddings" in m for m in messages)

    def test_model_load_failure_raises_runtime_error(self, fake_st):
        fake_st.fail_init = OSError("model files not found (offline)")
        indexer = _indexer()
        with pytest.raises(RuntimeError) as excinfo:
            indexer._ensure_initialized()
        message = str(excinfo.value)
        assert MODEL in message
        assert "offline" in message
        assert "pip install sentence-transformers" in message
        assert isinstance(excinfo.value.__cause__, OSError)
        assert indexer._initialized is False
        assert MODEL not in DocumentIndexer._model_cache

    def test_missing_package_at_load_time_raises_runtime_error(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "sentence_transformers", None)
        monkeypatch.setattr(DocumentIndexer, "_model_cache", {})
        with pytest.raises(RuntimeError, match="Failed to load embedding model"):
            _indexer()._load_model()

    def test_counts(self, fake_st):
        indexer = _indexer()
        assert indexer.num_categories == len(PII_EXEMPLARS)
        assert indexer.num_exemplars == len(EXEMPLAR_PAIRS)
        assert indexer.num_indexed_chunks == 0


class TestExemplarCache:
    def test_cache_path_depends_on_model_and_texts(self, fake_st, tmp_path):
        indexer = _indexer()
        p1 = indexer._exemplar_cache_path(["a", "b"])
        p2 = indexer._exemplar_cache_path(["a", "c"])
        p3 = _indexer(model_name="other/model")._exemplar_cache_path(["a", "b"])
        assert p1 != p2 and p1 != p3
        assert p1.startswith(str(tmp_path / "home" / ".cache" / "pbd-toolkit"))
        assert os.path.basename(p1).startswith("exemplar_embeddings_fake_test-model_")

    def test_cache_miss_when_file_absent(self, fake_st):
        assert _indexer()._load_exemplar_cache(["x"]) is None

    def test_cache_ignored_when_row_count_mismatches(self, fake_st):
        indexer = _indexer()
        texts = ["one", "two"]
        path = indexer._exemplar_cache_path(texts)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        np.savez_compressed(path, embeddings=np.ones((3, DIM), dtype=np.float32))
        assert indexer._load_exemplar_cache(texts) is None

    def test_corrupt_cache_is_ignored_and_recomputed(self, fake_st, caplog):
        caplog.set_level(logging.DEBUG, logger=LOGGER_NAME)
        indexer = _indexer(verbose=True)
        texts = [t for _, t in EXEMPLAR_PAIRS]
        path = indexer._exemplar_cache_path(texts)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(b"definitely not an npz file")

        indexer._ensure_initialized()
        assert indexer._exemplar_embeddings.shape == (len(texts), DIM)
        assert len(fake_st.instances[0].calls) == 1  # recomputed via the model
        assert any(
            "Exemplar cache load failed" in r.getMessage() for r in _records(caplog)
        )

    def test_cache_save_failure_is_non_fatal(self, fake_st, tmp_path, caplog):
        caplog.set_level(logging.DEBUG, logger=LOGGER_NAME)
        # Make ~/.cache a *file* so that makedirs() fails.
        home = tmp_path / "home"
        home.mkdir()
        (home / ".cache").write_text("blocker")

        indexer = _indexer(verbose=True)
        indexer._ensure_initialized()
        assert indexer._exemplar_embeddings.shape[0] == len(EXEMPLAR_PAIRS)
        assert any(
            "Failed to cache exemplar embeddings" in r.getMessage()
            for r in _records(caplog)
        )


# ---------------------------------------------------------------------------
# Custom exemplars merged into the exemplar matrix
# ---------------------------------------------------------------------------


class TestCustomExemplarMerge:
    def test_new_category_becomes_detectable(self, fake_st, tmp_path):
        custom_text = "Projekt-Nr. ABC-1234 (intern)"
        cfg = tmp_path / "custom.json"
        cfg.write_text(json.dumps({"CUSTOM_PROJECT": [custom_text]}))
        fake_st.vectors[custom_text] = axis_vector(SPARE_AXIS)
        fake_st.vectors["query"] = axis_vector(SPARE_AXIS)

        indexer = _indexer(threshold=0.5, custom_exemplars_path=str(cfg))
        matches = indexer.detect("query")

        assert [m.category for m in matches] == ["CUSTOM_PROJECT"]
        assert matches[0].score == pytest.approx(1.0)
        assert matches[0].best_exemplar == custom_text
        assert indexer._exemplar_embeddings.shape[0] == len(EXEMPLAR_PAIRS) + 1
        assert indexer._exemplar_categories[-1] == "CUSTOM_PROJECT"
        # Built-in categories are untouched by an unrelated custom category.
        assert indexer._exemplar_categories[: len(EXEMPLAR_PAIRS)] == [
            c for c, _ in EXEMPLAR_PAIRS
        ]

    def test_existing_category_is_extended(self, fake_st, tmp_path):
        extra = "Weitere E-Mail: someone@example.org"
        cfg = tmp_path / "custom.json"
        cfg.write_text(json.dumps({"VECTOR_EMAIL": [extra]}))
        fake_st.vectors[extra] = axis_vector(SPARE_AXIS)
        fake_st.vectors["q"] = axis_vector(SPARE_AXIS)

        indexer = _indexer(threshold=0.5, custom_exemplars_path=str(cfg))
        matches = indexer.detect("q")

        assert [m.category for m in matches] == ["VECTOR_EMAIL"]
        assert matches[0].best_exemplar == extra
        email_texts = [
            t
            for c, t in zip(indexer._exemplar_categories, indexer._exemplar_texts)
            if c == "VECTOR_EMAIL"
        ]
        assert email_texts == PII_EXEMPLARS["VECTOR_EMAIL"] + [extra]

    def test_unloadable_custom_file_keeps_builtin_exemplars(self, fake_st, caplog):
        caplog.set_level(logging.WARNING, logger=LOGGER_NAME)
        indexer = _indexer(custom_exemplars_path="/nonexistent/custom.json")
        indexer._ensure_initialized()
        assert indexer._exemplar_embeddings.shape[0] == len(EXEMPLAR_PAIRS)
        assert any("not found" in r.getMessage() for r in _records(caplog))


class TestCustomExemplarLoadingErrors:
    def test_yaml_file_loads_with_pyyaml(self, fake_st, tmp_path):
        cfg = tmp_path / "custom.yaml"
        cfg.write_text("CUSTOM_A:\n  - alpha\n  - beta\nCUSTOM_B: [gamma]\n")
        result = _indexer()._load_custom_exemplars(str(cfg))
        assert result == {"CUSTOM_A": ["alpha", "beta"], "CUSTOM_B": ["gamma"]}

    def test_yml_extension_without_pyyaml_warns(self, monkeypatch, tmp_path, caplog):
        caplog.set_level(logging.WARNING, logger=LOGGER_NAME)
        cfg = tmp_path / "custom.yml"
        cfg.write_text("A: [x]\n")
        monkeypatch.setitem(sys.modules, "yaml", None)
        result = _indexer()._load_custom_exemplars(str(cfg))
        assert result == {}
        assert any("PyYAML not installed" in r.getMessage() for r in _records(caplog))

    def test_malformed_json_warns_and_returns_empty(self, tmp_path, caplog):
        caplog.set_level(logging.WARNING, logger=LOGGER_NAME)
        cfg = tmp_path / "broken.json"
        cfg.write_text("{not json")
        assert _indexer()._load_custom_exemplars(str(cfg)) == {}
        assert any(
            "Failed to load custom exemplars" in r.getMessage()
            for r in _records(caplog)
        )

    def test_non_mapping_yaml_warns(self, tmp_path, caplog):
        caplog.set_level(logging.WARNING, logger=LOGGER_NAME)
        cfg = tmp_path / "list.yaml"
        cfg.write_text("- a\n- b\n")
        assert _indexer()._load_custom_exemplars(str(cfg)) == {}
        assert any(
            "must be a mapping" in r.getMessage() and "list" in r.getMessage()
            for r in _records(caplog)
        )

    def test_verbose_reports_category_count(self, tmp_path, caplog):
        caplog.set_level(logging.DEBUG, logger=LOGGER_NAME)
        cfg = tmp_path / "custom.json"
        cfg.write_text(json.dumps({"A": ["x"], "B": ["y"], "BAD": "not-a-list"}))
        result = _indexer(verbose=True)._load_custom_exemplars(str(cfg))
        assert set(result) == {"A", "B"}
        assert any(
            "Loaded 2 custom exemplar categories" in r.getMessage()
            for r in _records(caplog)
        )


# ---------------------------------------------------------------------------
# Embedding and inline detection
# ---------------------------------------------------------------------------


class TestEmbedding:
    def test_embed_text_returns_unit_float32_vector(self, fake_st):
        fake_st.vectors["scaled"] = np.full(DIM, 3.0, dtype=np.float32)
        vec = _indexer().embed_text("scaled")
        assert vec.dtype == np.float32
        assert vec.shape == (DIM,)
        assert np.linalg.norm(vec) == pytest.approx(1.0, abs=1e-6)
        np.testing.assert_allclose(vec, np.full(DIM, 1 / math.sqrt(DIM)), atol=1e-6)

    def test_embed_text_initialises_lazily(self, fake_st):
        indexer = _indexer()
        indexer.embed_text("anything")
        assert indexer._initialized is True
        # exemplar batch first, then the single query text
        assert fake_st.instances[0].calls[-1] == ["anything"]

    def test_unknown_text_is_orthogonal_to_all_exemplars(self, fake_st):
        indexer = _indexer()
        vec = indexer.embed_text("lorem ipsum dolor sit amet")
        sims = indexer._exemplar_embeddings @ vec
        assert np.abs(sims).max() < 1e-6


class TestDetect:
    def test_single_category_match(self, fake_st):
        text = "Schreiben Sie an: erika@example.de"
        fake_st.vectors[text] = pii_vector("VECTOR_EMAIL", 0.9)
        indexer = _indexer(threshold=0.75)

        matches = indexer.detect(text)

        assert len(matches) == 1
        match = matches[0]
        assert isinstance(match, CategoryMatch)
        assert match.category == "VECTOR_EMAIL"
        assert match.score == pytest.approx(0.9, abs=1e-6)
        assert match.best_exemplar == PII_EXEMPLARS["VECTOR_EMAIL"][0]

    def test_multiple_categories_sorted_by_score(self, fake_st):
        text = "email and phone"
        v = np.zeros(DIM, dtype=np.float32)
        v[CATEGORIES.index("VECTOR_PHONE")] = 0.6
        v[CATEGORIES.index("VECTOR_EMAIL")] = 0.8
        fake_st.vectors[text] = v
        indexer = _indexer(threshold=0.5)

        matches = indexer.detect(text)

        assert [m.category for m in matches] == ["VECTOR_EMAIL", "VECTOR_PHONE"]
        assert [round(m.score, 4) for m in matches] == [0.8, 0.6]
        assert matches[0].best_exemplar == PII_EXEMPLARS["VECTOR_EMAIL"][0]
        assert matches[1].best_exemplar == PII_EXEMPLARS["VECTOR_PHONE"][0]

    def test_below_threshold_returns_empty(self, fake_st):
        fake_st.vectors["weak"] = pii_vector("VECTOR_SSN", 0.7)
        assert _indexer(threshold=0.75).detect("weak") == []

    def test_score_exactly_at_threshold_is_included(self, fake_st):
        fake_st.vectors["edge"] = pii_vector("VECTOR_HEALTH", 1.0)
        matches = _indexer(threshold=1.0).detect("edge")
        assert [m.category for m in matches] == ["VECTOR_HEALTH"]
        assert matches[0].score == pytest.approx(1.0)

    def test_threshold_override_per_call(self, fake_st):
        fake_st.vectors["t"] = pii_vector("VECTOR_FINANCIAL", 0.6)
        indexer = _indexer(threshold=0.9)
        assert indexer.detect("t") == []
        lowered = indexer.detect("t", threshold=0.5)
        assert [m.category for m in lowered] == ["VECTOR_FINANCIAL"]
        # Instance threshold is left untouched by the override.
        assert indexer.threshold == 0.9
        assert indexer.detect("t") == []

    def test_unrelated_text_yields_no_match(self, fake_st):
        assert _indexer(threshold=0.1).detect("the weather is nice today") == []

    def test_query_pii_categories_with_prepared_embedding(self, fake_st):
        indexer = _indexer(threshold=0.75)
        emb = pii_vector("VECTOR_VEHICLE", 0.8)
        matches = indexer.query_pii_categories(emb)
        assert [m.category for m in matches] == ["VECTOR_VEHICLE"]
        assert indexer.query_pii_categories(emb, threshold=0.85) == []

    def test_all_categories_reported_with_zero_threshold(self, fake_st):
        fake_st.vectors["x"] = pii_vector("VECTOR_PERSON", 1.0)
        matches = _indexer(threshold=0.0).detect("x")
        # one match per category, best first
        assert len(matches) == len(PII_EXEMPLARS)
        assert matches[0].category == "VECTOR_PERSON"
        assert len({m.category for m in matches}) == len(PII_EXEMPLARS)


# ---------------------------------------------------------------------------
# Full-document index: add_chunk + query_similar_chunks
# ---------------------------------------------------------------------------


def _register_docs(fake_st) -> None:
    """Three documents with known geometry relative to the query 'q'."""
    e0, e1, e2 = axis_vector(0), axis_vector(1), axis_vector(2)
    fake_st.vectors["doc identical"] = e0
    fake_st.vectors["doc halfway"] = (e0 + e1) / math.sqrt(2)
    fake_st.vectors["doc unrelated"] = e2
    fake_st.vectors["q"] = e0


class TestFullIndexBruteForce:
    def test_add_chunk_embeds_and_stores(self, fake_st):
        fake_st.vectors["chunk"] = np.full(DIM, 2.0, dtype=np.float32)
        indexer = _indexer()
        indexer.add_chunk("chunk", file_path="/a.txt", chunk_idx=3, file_hash="h1")

        assert indexer.num_indexed_chunks == 1
        chunk = indexer._chunks[0]
        assert isinstance(chunk, IndexedChunk)
        assert (chunk.file_path, chunk.chunk_idx, chunk.text, chunk.file_hash) == (
            "/a.txt",
            3,
            "chunk",
            "h1",
        )
        assert np.linalg.norm(chunk.embedding) == pytest.approx(1.0, abs=1e-6)
        assert indexer._faiss_index is None

    def test_query_ranks_filters_and_truncates(self, fake_st):
        _register_docs(fake_st)
        indexer = _indexer()
        indexer.add_chunk("doc unrelated", file_path="/c.txt", chunk_idx=0)
        indexer.add_chunk("doc halfway", file_path="/b.txt", chunk_idx=0)
        indexer.add_chunk("doc identical", file_path="/a.txt", chunk_idx=0)

        results = indexer.query_similar_chunks("q", top_k=5, threshold=0.5)
        assert [c.file_path for _, c in results] == ["/a.txt", "/b.txt"]
        assert results[0][0] == pytest.approx(1.0)
        assert results[1][0] == pytest.approx(1 / math.sqrt(2), abs=1e-6)

        assert [c.text for _, c in indexer.query_similar_chunks("q", top_k=1)] == [
            "doc identical"
        ]
        everything = indexer.query_similar_chunks("q", top_k=10, threshold=-1.0)
        assert [c.text for _, c in everything] == [
            "doc identical",
            "doc halfway",
            "doc unrelated",
        ]
        assert everything[-1][0] == pytest.approx(0.0, abs=1e-6)

    def test_query_on_empty_index_does_not_embed(self, fake_st):
        indexer = _indexer()
        assert indexer.query_similar_chunks("q") == []
        assert fake_st.instances == []  # nothing initialised at all

    def test_concurrent_add_chunk_is_thread_safe(self, fake_st):
        indexer = _indexer()
        indexer._ensure_initialized()

        def worker(n: int) -> None:
            for i in range(20):
                indexer.add_chunk(f"t{n}-{i}", file_path=f"/f{n}.txt", chunk_idx=i)

        threads = [threading.Thread(target=worker, args=(n,)) for n in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert indexer.num_indexed_chunks == 80
        assert {c.file_path for c in indexer._chunks} == {
            f"/f{n}.txt" for n in range(4)
        }


class TestFullIndexWithFaiss:
    def test_add_chunk_also_feeds_faiss_index(self, fake_st, fake_faiss):
        _register_docs(fake_st)
        indexer = _indexer()
        indexer._faiss_index = fake_faiss.IndexFlatIP(DIM)
        indexer.add_chunk("doc identical", file_path="/a.txt")
        indexer.add_chunk("doc halfway", file_path="/b.txt")
        indexer.add_chunk("doc unrelated", file_path="/c.txt")

        assert indexer._faiss_index.ntotal == 3
        np.testing.assert_allclose(
            indexer._faiss_index.reconstruct(1), indexer._chunks[1].embedding
        )

        results = indexer.query_similar_chunks("q", top_k=5, threshold=0.5)
        assert [c.file_path for _, c in results] == ["/a.txt", "/b.txt"]
        assert results[0][0] == pytest.approx(1.0)
        assert results[1][0] == pytest.approx(1 / math.sqrt(2), abs=1e-6)
        assert all(isinstance(s, float) for s, _ in results)

    def test_faiss_search_respects_top_k(self, fake_st, fake_faiss):
        _register_docs(fake_st)
        indexer = _indexer()
        indexer._faiss_index = fake_faiss.IndexFlatIP(DIM)
        for text in ("doc identical", "doc halfway", "doc unrelated"):
            indexer.add_chunk(text, file_path=text)
        results = indexer.query_similar_chunks("q", top_k=1, threshold=0.0)
        assert [c.text for _, c in results] == ["doc identical"]

    def test_faiss_add_failure_is_logged_but_chunk_kept(
        self, fake_st, fake_faiss, caplog
    ):
        caplog.set_level(logging.WARNING, logger=LOGGER_NAME)

        class BrokenIndex(FakeIndexFlatIP):
            def add(self, x):
                raise RuntimeError("dimension mismatch")

        indexer = _indexer()
        indexer._faiss_index = BrokenIndex(DIM)
        indexer.add_chunk("chunk", file_path="/a.txt")
        assert indexer.num_indexed_chunks == 1
        assert indexer._faiss_index.ntotal == 0
        assert any(
            "FAISS add failed" in r.getMessage()
            and "dimension mismatch" in r.getMessage()
            for r in _records(caplog)
        )

    def test_faiss_search_edge_cases(self, fake_st, fake_faiss):
        indexer = _indexer()
        indexer._initialized = True
        query = axis_vector(0)

        # No faiss index at all
        assert indexer._faiss_search(query, top_k=5, threshold=0.0) == []

        # Index present but empty
        indexer._faiss_index = fake_faiss.IndexFlatIP(DIM)
        indexer._chunks = [
            IndexedChunk(file_path="/a", chunk_idx=0, text="a", embedding=None)
        ]
        assert indexer._faiss_search(query, top_k=5, threshold=0.0) == []

        # Stale index: more vectors than chunks -> out-of-range ids are skipped
        indexer._faiss_index.add(np.stack([axis_vector(1), axis_vector(0)]))
        results = indexer._faiss_search(query, top_k=5, threshold=-1.0)
        assert [c.text for _, c in results] == ["a"]
        assert results[0][0] == pytest.approx(0.0, abs=1e-6)


# ---------------------------------------------------------------------------
# Persistence: save_index / _load_faiss_index / _resolve_embedding
# ---------------------------------------------------------------------------


class TestSaveIndex:
    def test_skipped_without_path_or_chunks(self, fake_st, fake_faiss, tmp_path):
        indexer = _indexer()
        indexer.add_chunk("text", file_path="/a.txt")
        indexer.save_index()  # no path configured
        assert list(tmp_path.iterdir()) == [tmp_path / "home"]

        empty = _indexer(save_index_path=str(tmp_path / "empty"))
        empty.save_index()
        assert not (tmp_path / "empty.faiss").exists()
        assert not (tmp_path / "empty.meta").exists()

    def test_writes_faiss_and_meta(self, fake_st, fake_faiss, tmp_path, caplog):
        caplog.set_level(logging.DEBUG, logger=LOGGER_NAME)
        _register_docs(fake_st)
        target = tmp_path / "out" / "nested" / "idx"
        indexer = _indexer(save_index_path=str(target), verbose=True)
        indexer.add_chunk(
            "doc identical", file_path="/a.txt", chunk_idx=0, file_hash="h"
        )
        indexer.add_chunk("doc halfway", file_path="/a.txt", chunk_idx=1, file_hash="h")

        indexer.save_index()

        faiss_file = tmp_path / "out" / "nested" / "idx.faiss"
        meta_file = tmp_path / "out" / "nested" / "idx.meta"
        assert faiss_file.is_file() and meta_file.is_file()
        assert oct(faiss_file.stat().st_mode & 0o777) == oct(0o600)
        assert oct(meta_file.stat().st_mode & 0o777) == oct(0o600)

        stored = fake_faiss.read_index(str(faiss_file))
        assert stored.ntotal == 2
        np.testing.assert_allclose(stored.reconstruct(0), axis_vector(0), atol=1e-6)
        meta = json.loads(meta_file.read_text())
        assert meta == [
            {
                "file_path": "/a.txt",
                "chunk_idx": 0,
                "text": "doc identical",
                "file_hash": "h",
            },
            {
                "file_path": "/a.txt",
                "chunk_idx": 1,
                "text": "doc halfway",
                "file_hash": "h",
            },
        ]
        messages = [r.getMessage() for r in _records(caplog)]
        assert any("Index saved to" in m and "(2 chunks)" in m for m in messages)
        assert any("contains the raw text" in m for m in messages)

    def test_explicit_path_overrides_configured_one(
        self, fake_st, fake_faiss, tmp_path
    ):
        indexer = _indexer(save_index_path=str(tmp_path / "configured"))
        indexer.add_chunk("t", file_path="/a.txt")
        indexer.save_index(str(tmp_path / "explicit"))
        assert (tmp_path / "explicit.faiss").exists()
        assert not (tmp_path / "configured.faiss").exists()

    def test_no_text_warning_when_store_text_disabled(
        self, fake_st, fake_faiss, tmp_path, caplog
    ):
        caplog.set_level(logging.WARNING, logger=LOGGER_NAME)
        indexer = _indexer(save_index_path=str(tmp_path / "idx"), store_text=False)
        indexer.add_chunk("secret", file_path="/a.txt", file_hash="abc")
        indexer.save_index()
        meta = json.loads((tmp_path / "idx.meta").read_text())
        assert meta == [
            {"file_path": "/a.txt", "chunk_idx": 0, "text": "", "file_hash": "abc"}
        ]
        assert not any("raw text" in r.getMessage() for r in _records(caplog))

    def test_missing_faiss_logs_warning(self, fake_st, no_faiss, tmp_path, caplog):
        caplog.set_level(logging.WARNING, logger=LOGGER_NAME)
        indexer = _indexer(save_index_path=str(tmp_path / "idx"))
        indexer.add_chunk("t", file_path="/a.txt")
        indexer.save_index()
        assert not (tmp_path / "idx.faiss").exists()
        assert not (tmp_path / "idx.meta").exists()
        assert any(
            "faiss-cpu not installed; index not saved" in r.getMessage()
            for r in _records(caplog)
        )

    def test_write_failure_logs_warning(self, fake_st, fake_faiss, tmp_path, caplog):
        caplog.set_level(logging.WARNING, logger=LOGGER_NAME)

        def boom(index, path):
            raise OSError("disk full")

        fake_faiss.write_index = boom
        indexer = _indexer(save_index_path=str(tmp_path / "idx"))
        indexer.add_chunk("t", file_path="/a.txt")
        indexer.save_index()
        assert not (tmp_path / "idx.meta").exists()
        assert any(
            "Failed to save index" in r.getMessage() and "disk full" in r.getMessage()
            for r in _records(caplog)
        )

    def test_orphan_chunk_without_embedding_fails_softly(
        self, fake_st, fake_faiss, tmp_path, caplog
    ):
        caplog.set_level(logging.WARNING, logger=LOGGER_NAME)
        indexer = _indexer(save_index_path=str(tmp_path / "idx"))
        indexer._initialized = True
        indexer._chunks = [
            IndexedChunk(file_path="/o.txt", chunk_idx=0, text="o", embedding=None)
        ]
        indexer.save_index()
        assert any(
            "Failed to save index" in r.getMessage()
            and "no FAISS index is loaded" in r.getMessage()
            for r in _records(caplog)
        )


def _write_index_files(fake_faiss, prefix, vectors, meta) -> None:
    index = fake_faiss.IndexFlatIP(vectors.shape[1])
    index.add(vectors)
    fake_faiss.write_index(index, str(prefix) + ".faiss")
    with open(str(prefix) + ".meta", "w", encoding="utf-8") as fh:
        json.dump(meta, fh)


class TestLoadFaissIndex:
    def test_query_loads_a_configured_index_on_first_use(
        self, fake_st, fake_faiss, tmp_path
    ):
        """Regression: ``query_similar_chunks`` used to return early on the empty
        ``_chunks`` list *before* anything triggered ``_ensure_initialized()``,
        so a freshly constructed indexer with ``load_index_path`` never loaded
        its index and ``pbd-toolkit query`` always reported zero results.
        """
        prefix = tmp_path / "idx"
        _write_index_files(
            fake_faiss,
            prefix,
            np.stack([axis_vector(1)]),
            [{"file_path": "/b.txt", "chunk_idx": 0, "text": "B"}],
        )
        fake_st.vectors["q"] = axis_vector(1)

        indexer = _indexer(load_index_path=str(prefix))
        assert indexer.is_available() is True
        assert indexer._initialized is False

        hits = indexer.query_similar_chunks("q", top_k=5, threshold=0.5)

        assert indexer._initialized is True
        assert [c.text for _, c in hits] == ["B"]
        assert indexer.num_indexed_chunks == 1

    def test_query_without_load_path_does_not_initialise_for_an_empty_index(
        self, fake_st
    ):
        indexer = _indexer()
        assert indexer.query_similar_chunks("q", top_k=5, threshold=0.5) == []
        assert indexer._initialized is False

    def test_loaded_on_initialisation_and_queryable(
        self, fake_st, fake_faiss, tmp_path, caplog
    ):
        caplog.set_level(logging.DEBUG, logger=LOGGER_NAME)
        prefix = tmp_path / "idx"
        _write_index_files(
            fake_faiss,
            prefix,
            np.stack([axis_vector(0), axis_vector(1)]),
            [
                {"file_path": "/a.txt", "chunk_idx": 0, "text": "A", "file_hash": "ha"},
                {"file_path": "/b.txt", "chunk_idx": 4, "text": "B"},
            ],
        )
        fake_st.vectors["q"] = axis_vector(1)

        indexer = _indexer(load_index_path=str(prefix), verbose=True)
        indexer._ensure_initialized()
        results = indexer.query_similar_chunks("q", top_k=5, threshold=0.5)

        assert indexer._initialized is True
        assert indexer._faiss_index.ntotal == 2
        assert [(c.file_path, c.chunk_idx, c.text) for c in indexer._chunks] == [
            ("/a.txt", 0, "A"),
            ("/b.txt", 4, "B"),
        ]
        assert all(c.embedding is None for c in indexer._chunks)
        assert indexer.get_indexed_file_hashes() == {"/a.txt": "ha"}
        assert [(round(s, 6), c.text) for s, c in results] == [(1.0, "B")]
        assert any(
            "Loaded index from" in r.getMessage() and "(2 chunks)" in r.getMessage()
            for r in _records(caplog)
        )

    def test_load_add_resave_round_trip(self, fake_st, fake_faiss, tmp_path):
        prefix = tmp_path / "idx"
        _write_index_files(
            fake_faiss,
            prefix,
            np.stack([axis_vector(0)]),
            [
                {
                    "file_path": "/old.txt",
                    "chunk_idx": 0,
                    "text": "old",
                    "file_hash": "h0",
                }
            ],
        )
        fake_st.vectors["new chunk"] = axis_vector(2)

        indexer = _indexer(
            load_index_path=str(prefix), save_index_path=str(tmp_path / "idx2")
        )
        indexer.add_chunk(
            "new chunk", file_path="/new.txt", chunk_idx=0, file_hash="h1"
        )
        assert indexer._faiss_index.ntotal == 2
        assert indexer.get_indexed_file_hashes() == {"/old.txt": "h0", "/new.txt": "h1"}

        indexer.save_index()
        resaved = fake_faiss.read_index(str(tmp_path / "idx2.faiss"))
        assert resaved.ntotal == 2
        np.testing.assert_allclose(resaved.reconstruct(0), axis_vector(0), atol=1e-6)
        np.testing.assert_allclose(resaved.reconstruct(1), axis_vector(2), atol=1e-6)
        meta = json.loads((tmp_path / "idx2.meta").read_text())
        assert [m["file_path"] for m in meta] == ["/old.txt", "/new.txt"]

    def test_missing_files_start_fresh(self, fake_st, fake_faiss, tmp_path, caplog):
        caplog.set_level(logging.WARNING, logger=LOGGER_NAME)
        indexer = _indexer(load_index_path=str(tmp_path / "missing"))
        indexer._ensure_initialized()
        assert indexer._chunks == []
        assert indexer._faiss_index is None
        assert indexer._initialized is True
        assert any(
            "Index files not found" in r.getMessage()
            and "starting fresh" in r.getMessage()
            for r in _records(caplog)
        )

    def test_missing_meta_file_starts_fresh(
        self, fake_st, fake_faiss, tmp_path, caplog
    ):
        caplog.set_level(logging.WARNING, logger=LOGGER_NAME)
        prefix = tmp_path / "idx"
        index = fake_faiss.IndexFlatIP(DIM)
        index.add(axis_vector(0))
        fake_faiss.write_index(index, str(prefix) + ".faiss")

        indexer = _indexer()
        indexer._load_faiss_index(str(prefix))
        assert indexer._chunks == []
        assert any("Index files not found" in r.getMessage() for r in _records(caplog))

    def test_missing_faiss_package_logs_warning(self, no_faiss, tmp_path, caplog):
        caplog.set_level(logging.WARNING, logger=LOGGER_NAME)
        indexer = _indexer()
        indexer._load_faiss_index(str(tmp_path / "idx"))
        assert indexer._chunks == []
        assert indexer._faiss_index is None
        assert any(
            "faiss-cpu not installed; cannot load index" in r.getMessage()
            for r in _records(caplog)
        )

    def test_read_index_runtime_error_is_generic_failure(
        self, fake_faiss, tmp_path, caplog
    ):
        """Real faiss raises RuntimeError (not FileNotFoundError) on a missing
        file; that lands in the generic 'Failed to load index' branch."""
        caplog.set_level(logging.WARNING, logger=LOGGER_NAME)

        def read_index(path):
            raise RuntimeError(f"Error in faiss::FileIOReader: could not open {path}")

        fake_faiss.read_index = read_index
        indexer = _indexer()
        indexer._load_faiss_index(str(tmp_path / "idx"))
        assert indexer._chunks == []
        assert any(
            "Failed to load index" in r.getMessage()
            and "FileIOReader" in r.getMessage()
            for r in _records(caplog)
        )

    def test_corrupt_meta_logs_warning(self, fake_faiss, tmp_path, caplog):
        caplog.set_level(logging.WARNING, logger=LOGGER_NAME)
        prefix = tmp_path / "idx"
        index = fake_faiss.IndexFlatIP(DIM)
        index.add(axis_vector(0))
        fake_faiss.write_index(index, str(prefix) + ".faiss")
        (tmp_path / "idx.meta").write_text("{corrupt")

        indexer = _indexer()
        indexer._load_faiss_index(str(prefix))
        assert indexer._chunks == []
        assert any("Failed to load index" in r.getMessage() for r in _records(caplog))

    def test_meta_missing_required_key_logs_warning(self, fake_faiss, tmp_path, caplog):
        caplog.set_level(logging.WARNING, logger=LOGGER_NAME)
        prefix = tmp_path / "idx"
        _write_index_files(
            fake_faiss,
            prefix,
            np.stack([axis_vector(0)]),
            [{"chunk_idx": 0, "text": "x"}],
        )
        indexer = _indexer()
        indexer._load_faiss_index(str(prefix))
        assert indexer._chunks == []
        assert any(
            "Failed to load index" in r.getMessage() and "file_path" in r.getMessage()
            for r in _records(caplog)
        )

    def test_corrupt_meta_leaves_faiss_index_attached(self, fake_faiss, tmp_path):
        """Documents current behaviour: when ``.meta`` cannot be parsed the
        FAISS index read just before stays attached to the indexer while
        ``_chunks`` is empty.  Chunks appended afterwards land at FAISS
        position >= 1 while their list position starts at 0, so
        ``_faiss_search`` cannot map hits back to those chunks."""
        prefix = tmp_path / "idx"
        index = fake_faiss.IndexFlatIP(DIM)
        index.add(axis_vector(0))
        fake_faiss.write_index(index, str(prefix) + ".faiss")
        (tmp_path / "idx.meta").write_text("[{not json")

        indexer = _indexer()
        indexer._load_faiss_index(str(prefix))
        assert indexer._chunks == []
        assert indexer._faiss_index is not None
        assert indexer._faiss_index.ntotal == 1


class TestResolveEmbedding:
    def test_in_memory_embedding_returned_as_is(self, fake_faiss):
        indexer = _indexer()
        emb = axis_vector(3)
        chunk = IndexedChunk(file_path="/a", chunk_idx=0, text="a", embedding=emb)
        assert indexer._resolve_embedding(0, chunk) is emb

    def test_none_embedding_without_index_raises(self):
        indexer = _indexer()
        chunk = IndexedChunk(file_path="/a", chunk_idx=0, text="a", embedding=None)
        with pytest.raises(RuntimeError, match="no FAISS index is loaded"):
            indexer._resolve_embedding(0, chunk)

    def test_none_embedding_reconstructed_by_position(self, fake_faiss):
        indexer = _indexer()
        indexer._faiss_index = fake_faiss.IndexFlatIP(DIM)
        indexer._faiss_index.add(np.stack([axis_vector(0), axis_vector(5)]))
        chunk = IndexedChunk(file_path="/b", chunk_idx=9, text="b", embedding=None)
        np.testing.assert_array_equal(
            indexer._resolve_embedding(1, chunk), axis_vector(5)
        )
