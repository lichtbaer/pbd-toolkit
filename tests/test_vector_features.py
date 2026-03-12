"""Tests for vector search extensions:
- Feature 1: Post-Scan Query CLI (query_similar_chunks + FAISS search path)
- Feature 2: Custom exemplars via YAML/JSON config
- Feature 3: File hash tracking in document index
"""

from __future__ import annotations

import json
import os
import tempfile

import numpy as np
import pytest

from core.indexer.document_indexer import DocumentIndexer, IndexedChunk


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_indexer(**kwargs) -> DocumentIndexer:
    """Return a DocumentIndexer without loading any model."""
    return DocumentIndexer(**kwargs)


def _inject_chunks(indexer: DocumentIndexer, chunks: list[IndexedChunk]) -> None:
    """Directly set chunks list (bypasses embedding for unit tests)."""
    indexer._chunks = list(chunks)
    indexer._initialized = True  # prevent real model load


def _make_chunk(
    text: str,
    file_path: str = "test.txt",
    chunk_idx: int = 0,
    file_hash: str = "",
    embedding: np.ndarray | None = None,
) -> IndexedChunk:
    if embedding is None:
        embedding = np.zeros(4, dtype=np.float32)
    return IndexedChunk(
        file_path=file_path,
        chunk_idx=chunk_idx,
        text=text,
        embedding=embedding,
        file_hash=file_hash,
    )


# ---------------------------------------------------------------------------
# Feature 1: IndexedChunk.file_hash field
# ---------------------------------------------------------------------------


class TestIndexedChunkFileHash:
    def test_file_hash_default_empty(self):
        chunk = _make_chunk("hello")
        assert chunk.file_hash == ""

    def test_file_hash_set(self):
        chunk = _make_chunk("hello", file_hash="abc123")
        assert chunk.file_hash == "abc123"


# ---------------------------------------------------------------------------
# Feature 1: query_similar_chunks uses FAISS when index loaded from disk
# ---------------------------------------------------------------------------


class TestQuerySimilarChunksWithFaiss:
    def test_uses_brute_force_when_no_faiss_index(self):
        """Without a FAISS index, brute-force numpy search is used."""
        indexer = _make_indexer()
        dim = 4
        # Two chunks: one similar to query, one orthogonal
        q = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        similar_emb = np.array([0.9, 0.1, 0.0, 0.0], dtype=np.float32)
        similar_emb /= np.linalg.norm(similar_emb)
        orthogonal_emb = np.array([0.0, 1.0, 0.0, 0.0], dtype=np.float32)

        _inject_chunks(
            indexer,
            [
                _make_chunk("similar text", embedding=similar_emb),
                _make_chunk("unrelated text", embedding=orthogonal_emb),
            ],
        )
        # Manually embed query
        indexer._initialized = True

        # Monkey-patch embed_text to return the query vector
        indexer.embed_text = lambda text: q

        results = indexer.query_similar_chunks("any query", top_k=5, threshold=0.5)
        assert len(results) == 1
        score, chunk = results[0]
        assert chunk.text == "similar text"
        assert score > 0.5

    def test_returns_empty_when_no_chunks(self):
        indexer = _make_indexer()
        indexer._initialized = True
        indexer.embed_text = lambda text: np.zeros(4, dtype=np.float32)
        results = indexer.query_similar_chunks("query", top_k=5, threshold=0.5)
        assert results == []

    def test_faiss_search_path_selected_when_faiss_index_set(self):
        """When _faiss_index is set, _faiss_search should be called, not _brute_force."""
        indexer = _make_indexer()
        indexer._initialized = True

        # Sentinel to detect which path is taken
        called_faiss = []
        called_brute = []

        original_faiss = indexer._faiss_search
        original_brute = indexer._brute_force_search

        def fake_faiss_search(q, top_k, threshold):
            called_faiss.append(True)
            return []

        def fake_brute_search(q, top_k, threshold):
            called_brute.append(True)
            return []

        indexer._faiss_search = fake_faiss_search
        indexer._brute_force_search = fake_brute_search

        # With _faiss_index set → faiss path
        indexer._faiss_index = object()
        indexer._chunks = [_make_chunk("x")]
        indexer.embed_text = lambda t: np.zeros(4, dtype=np.float32)

        indexer.query_similar_chunks("q", top_k=3, threshold=0.5)
        assert called_faiss, "Expected _faiss_search to be called"
        assert not called_brute, "Expected _brute_force_search NOT to be called"

        # Without _faiss_index → brute-force path
        called_faiss.clear()
        indexer._faiss_index = None
        indexer.query_similar_chunks("q", top_k=3, threshold=0.5)
        assert called_brute, "Expected _brute_force_search to be called"
        assert not called_faiss, "Expected _faiss_search NOT to be called"


# ---------------------------------------------------------------------------
# Feature 2: Custom exemplars via JSON / YAML
# ---------------------------------------------------------------------------


class TestCustomExemplars:
    def test_load_custom_exemplars_json(self, tmp_path):
        cfg = {
            "CUSTOM_PROJECT": ["Projekt-Nr. ABC-1234", "Project ID: XYZ-001"],
            "VECTOR_PERSON": ["Zusätzliche Person"],
        }
        f = tmp_path / "exemplars.json"
        f.write_text(json.dumps(cfg))

        indexer = _make_indexer(custom_exemplars_path=str(f))
        result = indexer._load_custom_exemplars(str(f))
        assert "CUSTOM_PROJECT" in result
        assert result["CUSTOM_PROJECT"] == cfg["CUSTOM_PROJECT"]
        assert "VECTOR_PERSON" in result

    def test_load_custom_exemplars_invalid_values_skipped(self, tmp_path):
        cfg = {
            "VALID": ["text1", "text2"],
            "INVALID_INT": 42,
            "INVALID_MIXED": ["ok", 123],
        }
        f = tmp_path / "bad.json"
        f.write_text(json.dumps(cfg))

        indexer = _make_indexer()
        result = indexer._load_custom_exemplars(str(f))
        # Only VALID should pass; INVALID_INT and INVALID_MIXED skipped
        assert "VALID" in result
        assert "INVALID_INT" not in result
        assert "INVALID_MIXED" not in result

    def test_load_custom_exemplars_missing_file(self):
        indexer = _make_indexer()
        result = indexer._load_custom_exemplars("/nonexistent/path.json")
        assert result == {}

    def test_load_custom_exemplars_non_dict_json(self, tmp_path):
        f = tmp_path / "list.json"
        f.write_text(json.dumps(["not", "a", "dict"]))

        indexer = _make_indexer()
        result = indexer._load_custom_exemplars(str(f))
        assert result == {}

    def test_custom_exemplars_path_stored_on_indexer(self, tmp_path):
        f = tmp_path / "ex.json"
        f.write_text("{}")
        indexer = _make_indexer(custom_exemplars_path=str(f))
        assert indexer.custom_exemplars_path == str(f)


# ---------------------------------------------------------------------------
# Feature 3: File hash tracking
# ---------------------------------------------------------------------------


class TestFileHashTracking:
    def test_add_chunk_stores_file_hash(self):
        indexer = _make_indexer()
        indexer._initialized = True

        embedding = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        indexer.embed_text = lambda t: embedding

        indexer.add_chunk("some text", file_path="a.txt", chunk_idx=0, file_hash="aabbcc")
        assert len(indexer._chunks) == 1
        assert indexer._chunks[0].file_hash == "aabbcc"

    def test_add_chunk_default_empty_hash(self):
        indexer = _make_indexer()
        indexer._initialized = True
        indexer.embed_text = lambda t: np.zeros(4, dtype=np.float32)

        indexer.add_chunk("text", file_path="b.txt")
        assert indexer._chunks[0].file_hash == ""

    def test_get_indexed_file_hashes_returns_only_hashed(self):
        indexer = _make_indexer()
        _inject_chunks(
            indexer,
            [
                _make_chunk("t1", file_path="f1.txt", file_hash="hash1"),
                _make_chunk("t2", file_path="f2.txt", file_hash=""),
                _make_chunk("t3", file_path="f1.txt", file_hash="hash1"),  # duplicate file
            ],
        )
        hashes = indexer.get_indexed_file_hashes()
        assert hashes == {"f1.txt": "hash1"}
        assert "f2.txt" not in hashes  # empty hash excluded

    def test_get_indexed_file_hashes_empty_index(self):
        indexer = _make_indexer()
        indexer._initialized = True
        assert indexer.get_indexed_file_hashes() == {}

    def test_meta_json_includes_file_hash(self, tmp_path):
        """save_index should write file_hash to the .meta JSON."""
        indexer = _make_indexer(save_index_path=str(tmp_path / "idx"))
        indexer._initialized = True

        # Pre-inject a chunk with hash
        embedding = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        _inject_chunks(
            indexer,
            [_make_chunk("sensitive text", file_path="doc.txt", file_hash="deadbeef", embedding=embedding)],
        )

        # save_index requires faiss; skip if not installed
        try:
            import faiss  # noqa: F401
        except ImportError:
            pytest.skip("faiss not installed")

        indexer.save_index()
        meta_path = str(tmp_path / "idx.meta")
        assert os.path.isfile(meta_path)
        with open(meta_path) as f:
            meta = json.load(f)
        assert meta[0]["file_hash"] == "deadbeef"

    def test_load_faiss_index_reads_file_hash(self, tmp_path):
        """_load_faiss_index should populate IndexedChunk.file_hash from meta."""
        meta = [
            {"file_path": "a.txt", "chunk_idx": 0, "text": "hello", "file_hash": "cafebabe"},
            {"file_path": "b.txt", "chunk_idx": 0, "text": "world"},  # no hash key (old format)
        ]
        meta_path = tmp_path / "idx.meta"
        meta_path.write_text(json.dumps(meta))

        # Create a minimal fake faiss index file to satisfy the loader
        try:
            import faiss
            dim = 4
            idx = faiss.IndexFlatIP(dim)
            idx.add(np.zeros((2, dim), dtype=np.float32))
            faiss.write_index(idx, str(tmp_path / "idx.faiss"))
        except ImportError:
            pytest.skip("faiss not installed")

        indexer = _make_indexer(load_index_path=str(tmp_path / "idx"))
        indexer._initialized = True
        indexer._load_faiss_index(str(tmp_path / "idx"))

        assert len(indexer._chunks) == 2
        assert indexer._chunks[0].file_hash == "cafebabe"
        assert indexer._chunks[1].file_hash == ""  # missing key → default


# ---------------------------------------------------------------------------
# VectorEngine.set_current_file
# ---------------------------------------------------------------------------


class TestVectorEngineSetCurrentFile:
    def _make_engine(self):
        from core.engines.vector_engine import VectorEngine

        class FakeConfig:
            use_vector_search = False
            use_vector_triage = False
            vector_threshold = 0.75
            vector_model = "sentence-transformers/all-MiniLM-L6-v2"
            vector_save_index = None
            vector_load_index = None
            vector_custom_exemplars = None
            verbose = False
            logger = None

        return VectorEngine(FakeConfig())

    def test_set_current_file_stores_context(self):
        engine = self._make_engine()
        engine.set_current_file("/data/secret.docx", "0123456789abcdef")
        assert engine._thread_local.file_path == "/data/secret.docx"
        assert engine._thread_local.file_hash == "0123456789abcdef"

    def test_set_current_file_default_hash(self):
        engine = self._make_engine()
        engine.set_current_file("/data/file.txt")
        assert engine._thread_local.file_path == "/data/file.txt"
        assert engine._thread_local.file_hash == ""

    def test_set_current_file_thread_local_isolation(self):
        """Each thread should have its own file context."""
        import threading

        engine = self._make_engine()
        results = {}

        def worker(name, path):
            engine.set_current_file(path)
            import time; time.sleep(0.01)
            results[name] = getattr(engine._thread_local, "file_path", None)

        t1 = threading.Thread(target=worker, args=("t1", "/path/a.txt"))
        t2 = threading.Thread(target=worker, args=("t2", "/path/b.txt"))
        t1.start(); t2.start()
        t1.join(); t2.join()

        assert results["t1"] == "/path/a.txt"
        assert results["t2"] == "/path/b.txt"
