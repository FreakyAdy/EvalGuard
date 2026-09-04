"""Semantic contamination detection using embedding cosine similarity."""

from __future__ import annotations

import logging
import math
from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any

logger = logging.getLogger(__name__)


def cosine_similarity(v1: Sequence[float], v2: Sequence[float]) -> float:
    """Compute cosine similarity between two numeric vectors."""
    if len(v1) != len(v2) or len(v1) == 0:
        return 0.0

    dot = sum(a * b for a, b in zip(v1, v2, strict=True))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))

    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    return float(dot / (norm1 * norm2))


class EmbeddingBackend(ABC):
    """Abstract interface for text embedding providers."""

    @abstractmethod
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Compute embedding vectors for a batch of strings."""
        ...


class SentenceTransformersBackend(EmbeddingBackend):
    """Offline embedding backend using sentence-transformers (all-MiniLM-L6-v2)."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        self.model_name = model_name
        self._model: Any = None

    def _load_model(self) -> Any:
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer(self.model_name)
            except ImportError as e:
                raise RuntimeError(
                    "sentence-transformers is not installed. Install with: pip install evalguard[semantic]"
                ) from e
        return self._model

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        model = self._load_model()
        embeddings = model.encode(texts, convert_to_numpy=True)
        return [vec.tolist() for vec in embeddings]


class SimpleTfIdfBackend(EmbeddingBackend):
    """Lightweight zero-dependency bag-of-words/character n-gram vectorizer for fallback."""

    def __init__(self) -> None:
        self.vocabulary: dict[str, int] = {}

    def _build_vocab(self, texts: list[str]) -> None:
        vocab: set[str] = set()
        for t in texts:
            words = t.lower().split()
            vocab.update(words)
        self.vocabulary = {w: idx for idx, w in enumerate(sorted(vocab))}

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not self.vocabulary:
            self._build_vocab(texts)

        vectors: list[list[float]] = []
        vocab_size = len(self.vocabulary)
        for t in texts:
            vec = [0.0] * vocab_size
            words = t.lower().split()
            for w in words:
                if w in self.vocabulary:
                    vec[self.vocabulary[w]] += 1.0
            norm = math.sqrt(sum(x * x for x in vec))
            if norm > 0:
                vec = [x / norm for x in vec]
            vectors.append(vec)
        return vectors


class SemanticDetector:
    """Detects semantic contamination by computing cosine similarity across embeddings."""

    def __init__(
        self,
        backend: EmbeddingBackend | None = None,
        similarity_threshold: float = 0.85,
    ) -> None:
        self.backend = backend or SentenceTransformersBackend()
        self.similarity_threshold = similarity_threshold

    def compare(self, candidate_text: str, reference_text: str) -> tuple[float, bool]:
        """Compute cosine similarity and return (similarity_score, is_contaminated)."""
        try:
            vectors = self.backend.embed_texts([candidate_text, reference_text])
        except Exception as e:
            logger.warning("Semantic embedding failed (%s), falling back to TF-IDF vectorizer", e)
            fallback = SimpleTfIdfBackend()
            vectors = fallback.embed_texts([candidate_text, reference_text])

        sim = cosine_similarity(vectors[0], vectors[1])
        is_contaminated = sim >= self.similarity_threshold
        return round(sim, 4), is_contaminated
