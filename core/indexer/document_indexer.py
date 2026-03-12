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
from typing import Optional, TYPE_CHECKING

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
        save_index_path: Optional[str] = None,
        load_index_path: Optional[str] = None,
        verbose: bool = False,
    ) -> None:
        self.model_name = model_name
        self.threshold = threshold
        self.save_index_path = save_index_path
        self.load_index_path = load_index_path
        self.verbose = verbose

        self._embed_lock = threading.Lock()
        self._model: Optional[object] = (
            None  # sentence-transformers SentenceTransformer
        )

        # Pre-computed exemplar matrix: shape (n_exemplars, embedding_dim)
        self._exemplar_embeddings: Optional[np.ndarray] = None
        self._exemplar_categories: list[str] = []
        self._exemplar_texts: list[str] = []

        # Full-document index (optional, FAISS-backed)
        self._chunks: list[IndexedChunk] = []
        self._faiss_index: Optional[object] = None  # faiss.Index
        self._index_lock = threading.Lock()

        self._initialized = False
        self._available: Optional[bool] = None

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
        """Embed all exemplar texts and build normalised reference matrix."""
        categories = [pair[0] for pair in EXEMPLAR_PAIRS]
        texts = [pair[1] for pair in EXEMPLAR_PAIRS]

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
        threshold: Optional[float] = None,
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

    def detect(
        self, text: str, threshold: Optional[float] = None
    ) -> list[CategoryMatch]:
        """Convenience method: embed *text* and return PII category matches."""
        embedding = self.embed_text(text)
        return self.query_pii_categories(embedding, threshold)

    # ------------------------------------------------------------------
    # Full-document index (optional, for cross-document analysis)
    # ------------------------------------------------------------------

    def add_chunk(self, text: str, file_path: str, chunk_idx: int = 0) -> None:
        """Embed *text* and add it to the in-memory document index.

        Call ``save_index()`` afterwards to persist to disk.
        """
        self._ensure_initialized()
        embedding = self.embed_text(text)
        chunk = IndexedChunk(
            file_path=file_path,
            chunk_idx=chunk_idx,
            text=text,
            embedding=embedding,
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

        Requires FAISS or falls back to brute-force numpy search.

        Returns:
            List of (similarity_score, IndexedChunk) sorted by score descending.
        """
        if not self._chunks:
            return []
        query_emb = self.embed_text(text)
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

    # ------------------------------------------------------------------
    # FAISS persistence
    # ------------------------------------------------------------------

    def save_index(self, path: Optional[str] = None) -> None:
        """Save the document index to *path* (FAISS + metadata pickle).

        Silently skipped if no chunks have been indexed or FAISS is unavailable.
        """
        target = path or self.save_index_path
        if not target or not self._chunks:
            return
        try:
            import faiss  # type: ignore
            import pickle

            os.makedirs(os.path.dirname(os.path.abspath(target)), exist_ok=True)
            matrix = np.stack([c.embedding for c in self._chunks])
            idx = faiss.IndexFlatIP(matrix.shape[1])
            idx.add(matrix)  # type: ignore[arg-type]
            faiss.write_index(idx, target + ".faiss")

            meta = [
                {"file_path": c.file_path, "chunk_idx": c.chunk_idx, "text": c.text}
                for c in self._chunks
            ]
            with open(target + ".meta", "wb") as fh:
                pickle.dump(meta, fh)

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
            import faiss  # type: ignore
            import pickle

            self._faiss_index = faiss.read_index(path + ".faiss")
            with open(path + ".meta", "rb") as fh:
                meta = pickle.load(fh)

            # Reconstruct chunk list (embeddings are in FAISS, not reloaded here)
            self._chunks = [
                IndexedChunk(
                    file_path=m["file_path"],
                    chunk_idx=m["chunk_idx"],
                    text=m["text"],
                    embedding=np.zeros(1, dtype=np.float32),  # placeholder
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

    @property
    def num_categories(self) -> int:
        return len(PII_EXEMPLARS)

    @property
    def num_exemplars(self) -> int:
        return len(EXEMPLAR_PAIRS)

    @property
    def num_indexed_chunks(self) -> int:
        return len(self._chunks)
