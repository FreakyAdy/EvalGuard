"""Semantic contamination detection using embedding cosine similarity."""

from __future__ import annotations

import logging
import math
from abc import ABC, abstractmethod
from collections.abc import Sequence
from pathlib import Path
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


class OnnxRuntimeBackend(EmbeddingBackend):
    """Local ONNX embedding backend with attention-mask mean pooling.

    Both the ONNX model and tokenizer must already exist locally. This backend
    deliberately disables tokenizer downloads so CI jobs and offline deployments
    do not unexpectedly contact a model hub.
    """

    def __init__(
        self,
        model_path: str | Path,
        tokenizer_path: str | Path | None = None,
        max_length: int = 256,
        providers: Sequence[str] | None = None,
        session: Any | None = None,
        tokenizer: Any | None = None,
    ) -> None:
        if isinstance(max_length, bool) or not isinstance(max_length, int) or max_length < 1:
            raise ValueError("max_length must be a positive integer")

        self.model_path = Path(model_path)
        self.tokenizer_path = Path(tokenizer_path) if tokenizer_path is not None else None
        self.max_length = max_length
        self.providers = list(providers) if providers is not None else ["CPUExecutionProvider"]
        self._session = session
        self._tokenizer = tokenizer

    def _load_session(self) -> Any:
        if self._session is None:
            if not self.model_path.is_file():
                raise FileNotFoundError(
                    f"ONNX model file does not exist: {self.model_path}"
                )
            try:
                import onnxruntime
            except ImportError as exc:
                raise RuntimeError(
                    "onnxruntime is not installed. Install with: pip install evalguard[onnx]"
                ) from exc
            self._session = onnxruntime.InferenceSession(
                str(self.model_path),
                providers=self.providers,
            )
        return self._session

    def _load_tokenizer(self) -> Any:
        if self._tokenizer is None:
            tokenizer_path = self.tokenizer_path or self.model_path.parent
            if not tokenizer_path.is_dir():
                raise FileNotFoundError(
                    f"Local tokenizer directory does not exist: {tokenizer_path}"
                )
            try:
                from transformers import AutoTokenizer
            except ImportError as exc:
                raise RuntimeError(
                    "transformers is not installed. Install with: pip install evalguard[onnx]"
                ) from exc
            try:
                self._tokenizer = AutoTokenizer.from_pretrained(
                    str(tokenizer_path),
                    local_files_only=True,
                )
            except Exception as exc:
                raise RuntimeError(
                    f"Could not load a tokenizer from local files at {tokenizer_path}"
                ) from exc
        return self._tokenizer

    @staticmethod
    def _to_nested_list(value: Any) -> Any:
        """Convert array-like inference output to ordinary Python lists."""
        return value.tolist() if hasattr(value, "tolist") else value

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed a text batch using local ONNX inference and masked mean pooling."""
        if not texts:
            return []

        session = self._load_session()
        tokenizer = self._load_tokenizer()
        tokens = tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=self.max_length,
            return_tensors="np",
        )

        input_names = [item.name for item in session.get_inputs()]
        missing = [name for name in input_names if name not in tokens]
        if missing:
            raise ValueError(
                "Tokenizer output is missing required ONNX inputs: " + ", ".join(missing)
            )
        input_feed = {name: tokens[name] for name in input_names}
        outputs = session.run(None, input_feed)
        output_names = [item.name.lower() for item in session.get_outputs()]

        if not outputs:
            raise ValueError("ONNX model returned no outputs")

        pooled: Any | None = None
        for index, name in enumerate(output_names[: len(outputs)]):
            if name in {"sentence_embedding", "sentence_embeddings", "embeddings"}:
                direct_embeddings = self._to_nested_list(outputs[index])
                if direct_embeddings and isinstance(direct_embeddings[0], (list, tuple)):
                    if not direct_embeddings[0] or not isinstance(
                        direct_embeddings[0][0], (list, tuple)
                    ):
                        pooled = direct_embeddings
                        break

        if pooled is None:
            hidden_index = (
                output_names.index("last_hidden_state")
                if "last_hidden_state" in output_names
                else 0
            )
            hidden_states = self._to_nested_list(outputs[hidden_index])
            if (
                not isinstance(hidden_states, (list, tuple))
                or not hidden_states
                or not isinstance(hidden_states[0], (list, tuple))
                or not hidden_states[0]
                or not isinstance(hidden_states[0][0], (list, tuple))
            ):
                raise ValueError(
                    "ONNX output must be sentence embeddings or token-level hidden states"
                )

            raw_mask = tokens.get("attention_mask")
            attention_mask = (
                self._to_nested_list(raw_mask)
                if raw_mask is not None
                else [[1] * len(row) for row in hidden_states]
            )
            if len(attention_mask) != len(hidden_states):
                raise ValueError("Attention-mask batch size does not match ONNX output")

            pooled = []
            for batch_index, token_vectors in enumerate(hidden_states):
                mask = attention_mask[batch_index]
                if len(mask) != len(token_vectors):
                    raise ValueError("Attention-mask sequence length does not match ONNX output")
                if not token_vectors or not token_vectors[0]:
                    raise ValueError("ONNX output contains an empty token embedding")
                vector_size = len(token_vectors[0])
                weighted_sum = [0.0] * vector_size
                token_count = 0.0
                for token_index, token_vector in enumerate(token_vectors):
                    if not mask[token_index]:
                        continue
                    if len(token_vector) != vector_size:
                        raise ValueError("ONNX token embeddings have inconsistent dimensions")
                    token_count += 1.0
                    for dim, value in enumerate(token_vector):
                        weighted_sum[dim] += float(value)
                pooled.append(
                    [value / token_count for value in weighted_sum]
                    if token_count
                    else [0.0] * vector_size
                )

        if len(pooled) != len(texts):
            raise ValueError(
                f"ONNX model returned {len(pooled)} vectors for {len(texts)} input texts"
            )
        return [[float(value) for value in vector] for vector in pooled]


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
    """Detect semantic contamination using an ordered embedding-backend fallback chain."""

    def __init__(
        self,
        backend: EmbeddingBackend | None = None,
        similarity_threshold: float = 0.85,
        fallback_backends: Sequence[EmbeddingBackend] | None = None,
    ) -> None:
        if not math.isfinite(similarity_threshold) or not 0.0 <= similarity_threshold <= 1.0:
            raise ValueError("similarity_threshold must be a finite number between 0 and 1")
        self.backend = backend if backend is not None else SentenceTransformersBackend()
        self.fallback_backends = tuple(fallback_backends or ())
        self.similarity_threshold = similarity_threshold

    def compare(self, candidate_text: str, reference_text: str) -> tuple[float, bool]:
        """Compute cosine similarity and return (similarity_score, is_contaminated)."""
        texts = [candidate_text, reference_text]
        vectors: list[list[float]] | None = None

        for backend in (self.backend, *self.fallback_backends):
            try:
                candidate_vectors = backend.embed_texts(texts)
                if len(candidate_vectors) != 2:
                    raise ValueError(
                        f"{type(backend).__name__} returned {len(candidate_vectors)} vectors; expected 2"
                    )
                vectors = candidate_vectors
                break
            except Exception as exc:
                logger.warning(
                    "Semantic embedding backend %s failed: %s",
                    type(backend).__name__,
                    exc,
                )

        if vectors is None:
            logger.warning("All configured semantic backends failed; using TF-IDF fallback")
            vectors = SimpleTfIdfBackend().embed_texts(texts)

        similarity = cosine_similarity(vectors[0], vectors[1])
        return round(similarity, 4), similarity >= self.similarity_threshold
