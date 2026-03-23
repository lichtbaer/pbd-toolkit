"""Document indexer for vector-based PII detection.

This module provides:
- Embedding of text chunks using sentence-transformers (local) or OpenAI embeddings
- Exemplar-based PII category detection via cosine similarity
- Optional persistence of the document index (FAISS) for cross-document analysis
"""

from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np

from core.indexer.pii_queries import EXEMPLAR_PAIRS, PII_EXEMPLARS

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Disable HuggingFace telemetry (consistent with the rest of the project)
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")


@dataclass
class CategoryMatch:
    """A PII category match from vector similarity search."""

    category: str
    score: float
    best_exemplar: str


@dataclass
class IndexedChunk:
    """A document chunk stored in the full-document index."""

    file_path: str
    chunk_idx: int
    text: str
    embedding: np.ndarray = field(repr=False)
    file_hash: str = ""  # SHA-256 of file content; empty if not tracked


class DocumentIndexer:
    """Embeds text and detects PII categories via exemplar similarity.

    Two operational modes:

    1. **Inline mode** (default): For each incoming text chunk, embed it and
       compare against pre-computed exemplar vectors. Returns categories whose
       max similarity exceeds ``threshold``. No persistent index required.

    2. **Full-index mode** (``save_index`` / ``load_index``): All processed
       chunks are also stored in a FAISS index, enabling cross-document queries
       after the scan completes. Requires ``faiss-cpu`` to be installed.

    Thread safety: the model is loaded once under a class-level lock and shared
    across all instances that use the same ``model_name``.
    """

    # Class-level model cache so multiple engine instances share one model
    _model_cache: dict[str, object] = {}
    _model_lock = threading.Lock()

    def __init__(
        self,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        threshold: float = 0.75,
        save_index_path: str | None = None,
        load_index_path: str | None = None,
        custom_exemplars_path: str | None = None,
        verbose: bool = False,
    ) -> None:
        self.model_name = model_name
        self.threshold = threshold
        self.save_index_path = save_index_path
        self.load_index_path = load_index_path
        self.custom_exemplars_path = custom_exemplars_path
        self.verbose = verbose

        self._embed_lock = threading.Lock()
        self._model: object | None = None  # sentence-transformers SentenceTransformer

        # Pre-computed exemplar matrix: shape (n_exemplars, embedding_dim)
        self._exemplar_embeddings: np.ndarray | None = None
        self._exemplar_categories: list[str] = []
        self._exemplar_texts: list[str] = []

        # Full-document index (optional, FAISS-backed)
        self._chunks: list[IndexedChunk] = []
        self._faiss_index: object | None = None  # faiss.Index
        self._index_lock = threading.Lock()

        self._initialized = False
        self._available: bool | None = None

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """Return True if sentence-transformers is importable."""
        if self._available is not None:
            return self._available
        try:
            import sentence_transformers  # noqa: F401

            self._available = True
        except ImportError:
            self._available = False
        return self._available

    # ------------------------------------------------------------------
    # Lazy initialisation
    # ------------------------------------------------------------------

    def _ensure_initialized(self) -> None:
        """Load model and pre-compute exemplar embeddings (once per instance)."""
        if self._initialized:
            return
        with self._embed_lock:
            if self._initialized:
                return
            self._load_model()
            self._precompute_exemplars()
            if self.load_index_path:
                self._load_faiss_index(self.load_index_path)
            self._initialized = True

    def _load_model(self) -> None:
        """Load (or retrieve cached) sentence-transformers model."""
        with DocumentIndexer._model_lock:
            if self.model_name not in DocumentIndexer._model_cache:
                if self.verbose:
                    logger.debug(f"[vector] Loading embedding model: {self.model_name}")
                try:
                    from sentence_transformers import SentenceTransformer

                    model = SentenceTransformer(self.model_name)
                    DocumentIndexer._model_cache[self.model_name] = model
                    if self.verbose:
                        logger.debug(f"[vector] Model loaded: {self.model_name}")
                except Exception as exc:
                    raise RuntimeError(
                        f"Failed to load embedding model '{self.model_name}': {exc}\n"
                        "Install with: pip install sentence-transformers"
                    ) from exc
            self._model = DocumentIndexer._model_cache[self.model_name]

    def _precompute_exemplars(self) -> None:
        """Embed all exemplar texts and build normalised reference matrix.

        Starts with the built-in exemplars from ``pii_queries.py`` and
        optionally merges additional exemplar texts from
        ``custom_exemplars_path`` (YAML or JSON).  Custom categories that
        share a name with a built-in category extend that category's exemplar
        list; unknown names create new detection categories.
        """
        # Start with built-in exemplars
        exemplars: dict[str, list[str]] = {k: list(v) for k, v in PII_EXEMPLARS.items()}

        # Merge custom exemplars if configured
        if self.custom_exemplars_path:
            custom = self._load_custom_exemplars(self.custom_exemplars_path)
            for category, texts in custom.items():
                if category in exemplars:
                    exemplars[category] = exemplars[category] + texts
                else:
                    exemplars[category] = texts

        categories: list[str] = []
        texts: list[str] = []
        for category, category_texts in exemplars.items():
            for text in category_texts:
                categories.append(category)
                texts.append(text)

        if self.verbose:
            logger.debug(f"[vector] Pre-computing {len(texts)} exemplar embeddings …")

        raw = self._embed_batch(texts)  # (n, dim)
        norms = np.linalg.norm(raw, axis=1, keepdims=True) + 1e-10
        self._exemplar_embeddings = raw / norms  # L2-normalised → dot = cosine sim
        self._exemplar_categories = categories
        self._exemplar_texts = texts

        if self.verbose:
            logger.debug(
                f"[vector] Exemplar matrix ready: {self._exemplar_embeddings.shape}"
            )

    def _load_custom_exemplars(self, path: str) -> dict[str, list[str]]:
        """Load custom PII exemplar texts from a YAML or JSON file.

        The file must be a mapping of category name → list of example strings.
        YAML format requires PyYAML (``pip install PyYAML``).

        Returns an empty dict on any error (non-fatal; built-in exemplars
        are always used regardless).
        """
        import json as _json

        try:
            if path.lower().endswith((".yaml", ".yml")):
                try:
                    import yaml  # type: ignore

                    with open(path, encoding="utf-8") as fh:
                        data = yaml.safe_load(fh)
                except ImportError:
                    logger.warning(
                        "[vector] PyYAML not installed; cannot load YAML exemplars. "
                        "Install with: pip install PyYAML"
                    )
                    return {}
            else:
                with open(path, encoding="utf-8") as fh:
                    data = _json.load(fh)

            if not isinstance(data, dict):
                logger.warning(
                    f"[vector] Custom exemplars file must be a mapping of "
                    f"category → [texts]; got {type(data).__name__}"
                )
                return {}

            result: dict[str, list[str]] = {}
            for key, val in data.items():
                if isinstance(val, list) and all(isinstance(t, str) for t in val):
                    result[str(key)] = val
                else:
                    logger.warning(
                        f"[vector] Skipping custom exemplar '{key}': "
                        f"value must be a list of strings"
                    )

            if self.verbose:
                logger.debug(
                    f"[vector] Loaded {len(result)} custom exemplar categories "
                    f"from {path}"
                )
            return result

        except FileNotFoundError:
            logger.warning(f"[vector] Custom exemplars file not found: {path}")
            return {}
        except Exception as exc:
            logger.warning(
                f"[vector] Failed to load custom exemplars from {path}: {exc}"
            )
            return {}

    # ------------------------------------------------------------------
    # Embedding
    # ------------------------------------------------------------------

    def _embed_batch(self, texts: list[str]) -> np.ndarray:
        """Embed a list of texts. Returns float32 ndarray of shape (n, dim)."""
        result = self._model.encode(  # type: ignore[union-attr]
            texts,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=False,
        )
        return np.array(result, dtype=np.float32)

    def embed_text(self, text: str) -> np.ndarray:
        """Embed a single text chunk and return a normalised float32 vector."""
        self._ensure_initialized()
        raw = self._embed_batch([text])[0]
        norm = np.linalg.norm(raw) + 1e-10
        return (raw / norm).astype(np.float32)

    # ------------------------------------------------------------------
    # Inline PII category detection
    # ------------------------------------------------------------------

    def query_pii_categories(
        self,
        embedding: np.ndarray,
        threshold: float | None = None,
    ) -> list[CategoryMatch]:
        """Find PII categories whose exemplars are similar to *embedding*.

        Args:
            embedding: Normalised query vector (from ``embed_text``).
            threshold: Similarity cut-off. Defaults to ``self.threshold``.

        Returns:
            List of CategoryMatch objects, sorted by score descending.
            Only categories with at least one exemplar above the threshold
            are returned; one match per category (highest exemplar score).
        """
        self._ensure_initialized()
        cutoff = threshold if threshold is not None else self.threshold

        # Cosine similarities: (n_exemplars,) because both sides are L2-normalised
        sims: np.ndarray = self._exemplar_embeddings @ embedding  # type: ignore[operator]

        # Aggregate: best similarity per category
        best: dict[str, tuple[float, str]] = {}
        for idx, sim in enumerate(sims.tolist()):
            cat = self._exemplar_categories[idx]
            if sim > best.get(cat, (-1.0, ""))[0]:
                best[cat] = (sim, self._exemplar_texts[idx])

        matches = [
            CategoryMatch(category=cat, score=score, best_exemplar=exemplar)
            for cat, (score, exemplar) in best.items()
            if score >= cutoff
        ]
        matches.sort(key=lambda m: m.score, reverse=True)
        return matches

    def detect(self, text: str, threshold: float | None = None) -> list[CategoryMatch]:
        """Convenience method: embed *text* and return PII category matches."""
        embedding = self.embed_text(text)
        return self.query_pii_categories(embedding, threshold)

    # ------------------------------------------------------------------
    # Full-document index (optional, for cross-document analysis)
    # ------------------------------------------------------------------

    def add_chunk(
        self, text: str, file_path: str, chunk_idx: int = 0, file_hash: str = ""
    ) -> None:
        """Embed *text* and add it to the in-memory document index.

        Args:
            text: Text content to embed and store.
            file_path: Absolute path of the source file.
            chunk_idx: Sequential chunk index within the file.
            file_hash: SHA-256 hex digest of the source file; used for
                incremental-scan checks.  Pass an empty string if not tracked.

        Call ``save_index()`` afterwards to persist to disk.
        """
        self._ensure_initialized()
        embedding = self.embed_text(text)
        chunk = IndexedChunk(
            file_path=file_path,
            chunk_idx=chunk_idx,
            text=text,
            embedding=embedding,
            file_hash=file_hash,
        )
        with self._index_lock:
            self._chunks.append(chunk)
            if self._faiss_index is not None:
                self._faiss_add(embedding)

    def query_similar_chunks(
        self,
        text: str,
        top_k: int = 5,
        threshold: float = 0.70,
    ) -> list[tuple[float, IndexedChunk]]:
        """Find the *top_k* indexed chunks most similar to *text*.

        Uses the FAISS index when available (required when the index was loaded
        from disk, since chunk embeddings are stored in FAISS rather than in
        the in-memory ``IndexedChunk.embedding`` field).  Falls back to
        brute-force numpy search for in-memory-only indices.

        Returns:
            List of (similarity_score, IndexedChunk) sorted by score descending.
        """
        if not self._chunks:
            return []
        query_emb = self.embed_text(text)
        if self._faiss_index is not None:
            return self._faiss_search(query_emb, top_k, threshold)
        return self._brute_force_search(query_emb, top_k, threshold)

    def _brute_force_search(
        self,
        query: np.ndarray,
        top_k: int,
        threshold: float,
    ) -> list[tuple[float, IndexedChunk]]:
        with self._index_lock:
            if not self._chunks:
                return []
            matrix = np.stack([c.embedding for c in self._chunks])  # (n, dim)
            sims = (matrix @ query).tolist()
            ranked = sorted(zip(sims, self._chunks), key=lambda x: x[0], reverse=True)
        return [(s, c) for s, c in ranked[:top_k] if s >= threshold]

    def _faiss_search(
        self,
        query: np.ndarray,
        top_k: int,
        threshold: float,
    ) -> list[tuple[float, IndexedChunk]]:
        """Search using the FAISS index.

        Used when the index was loaded from disk, where chunk embeddings are
        stored in FAISS rather than in the ``IndexedChunk.embedding`` field.
        """
        with self._index_lock:
            if self._faiss_index is None or not self._chunks:
                return []
            n = min(top_k, self._faiss_index.ntotal)
            if n == 0:
                return []
            scores, indices = self._faiss_index.search(query.reshape(1, -1), n)
            results: list[tuple[float, IndexedChunk]] = []
            for score, idx in zip(scores[0].tolist(), indices[0].tolist()):
                if idx < 0 or idx >= len(self._chunks):
                    continue
                if float(score) >= threshold:
                    results.append((float(score), self._chunks[idx]))
            results.sort(key=lambda x: x[0], reverse=True)
            return results

    # ------------------------------------------------------------------
    # FAISS persistence
    # ------------------------------------------------------------------

    def save_index(self, path: str | None = None) -> None:
        """Save the document index to *path* (FAISS + metadata JSON).

        Silently skipped if no chunks have been indexed or FAISS is unavailable.
        """
        target = path or self.save_index_path
        if not target or not self._chunks:
            return
        try:
            import json

            import faiss  # type: ignore

            os.makedirs(os.path.dirname(os.path.abspath(target)), exist_ok=True)
            matrix = np.stack([c.embedding for c in self._chunks])
            idx = faiss.IndexFlatIP(matrix.shape[1])
            idx.add(matrix)  # type: ignore[arg-type]
            faiss.write_index(idx, target + ".faiss")

            meta = [
                {
                    "file_path": c.file_path,
                    "chunk_idx": c.chunk_idx,
                    "text": c.text,
                    "file_hash": c.file_hash,
                }
                for c in self._chunks
            ]
            with open(target + ".meta", "w", encoding="utf-8") as fh:
                json.dump(meta, fh)

            if self.verbose:
                logger.debug(
                    f"[vector] Index saved to {target} ({len(self._chunks)} chunks)"
                )
        except ImportError:
            logger.warning("[vector] faiss-cpu not installed; index not saved.")
        except Exception as exc:
            logger.warning(f"[vector] Failed to save index: {exc}")

    def _load_faiss_index(self, path: str) -> None:
        """Load a previously saved FAISS index from *path*."""
        try:
            import json

            import faiss  # type: ignore

            self._faiss_index = faiss.read_index(path + ".faiss")
            with open(path + ".meta", encoding="utf-8") as fh:
                meta = json.load(fh)

            # Reconstruct chunk list (embeddings are in FAISS, not reloaded here)
            self._chunks = [
                IndexedChunk(
                    file_path=m["file_path"],
                    chunk_idx=m["chunk_idx"],
                    text=m["text"],
                    embedding=np.zeros(1, dtype=np.float32),  # placeholder
                    file_hash=m.get("file_hash", ""),
                )
                for m in meta
            ]
            if self.verbose:
                logger.debug(
                    f"[vector] Loaded index from {path} ({len(self._chunks)} chunks)"
                )
        except FileNotFoundError:
            logger.warning(f"[vector] Index files not found at {path}; starting fresh.")
        except ImportError:
            logger.warning("[vector] faiss-cpu not installed; cannot load index.")
        except Exception as exc:
            logger.warning(f"[vector] Failed to load index: {exc}")

    def _faiss_add(self, embedding: np.ndarray) -> None:
        """Add one vector to the FAISS index (must hold _index_lock)."""
        try:
            self._faiss_index.add(embedding.reshape(1, -1))  # type: ignore[union-attr]
        except Exception as exc:
            logger.warning(f"[vector] FAISS add failed: {exc}")

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def get_indexed_file_hashes(self) -> dict[str, str]:
        """Return a mapping of ``file_path → file_hash`` for all indexed chunks.

        Only includes entries for which a non-empty hash was recorded.
        Useful for incremental scanning: compare against current file hashes
        to determine which files need to be re-processed.
        """
        result: dict[str, str] = {}
        for chunk in self._chunks:
            if chunk.file_hash:
                result[chunk.file_path] = chunk.file_hash
        return result

    @property
    def num_categories(self) -> int:
        return len(PII_EXEMPLARS)

    @property
    def num_exemplars(self) -> int:
        return len(EXEMPLAR_PAIRS)

    @property
    def num_indexed_chunks(self) -> int:
        return len(self._chunks)
