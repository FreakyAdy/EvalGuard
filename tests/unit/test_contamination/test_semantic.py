"""Tests for semantic embedding backends and fallback order."""

from __future__ import annotations

from typing import Any

import pytest

from evalguard.contamination.semantic import (
    EmbeddingBackend,
    OnnxRuntimeBackend,
    SemanticDetector,
)


class _Metadata:
    def __init__(self, name: str) -> None:
        self.name = name


class _FakeTokenizer:
    def __init__(self) -> None:
        self.call_kwargs: dict[str, Any] = {}

    def __call__(self, texts: list[str], **kwargs: Any) -> dict[str, list[list[int]]]:
        self.call_kwargs = kwargs
        return {
            "input_ids": [[1, 2], [3, 0]],
            "attention_mask": [[1, 1], [1, 0]],
        }


class _FakeSession:
    def __init__(
        self,
        outputs: list[Any],
        output_names: list[str] | None = None,
    ) -> None:
        self.outputs = outputs
        self.output_names = output_names or ["last_hidden_state"]
        self.received_feed: dict[str, Any] | None = None

    def get_inputs(self) -> list[_Metadata]:
        return [_Metadata("input_ids"), _Metadata("attention_mask")]

    def get_outputs(self) -> list[_Metadata]:
        return [_Metadata(name) for name in self.output_names]

    def run(
        self,
        output_names: list[str] | None,
        input_feed: dict[str, Any],
    ) -> list[Any]:
        self.received_feed = input_feed
        return self.outputs


class _FailingBackend(EmbeddingBackend):
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("backend unavailable")


class _FixedBackend(EmbeddingBackend):
    def __init__(self, vectors: list[list[float]]) -> None:
        self.vectors = vectors
        self.calls = 0

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        return self.vectors


def test_onnx_backend_mean_pools_tokens_and_ignores_padding() -> None:
    tokenizer = _FakeTokenizer()
    session = _FakeSession(
        [
            [
                [[1.0, 0.0], [3.0, 0.0]],
                [[0.0, 1.0], [0.0, 10.0]],
            ]
        ]
    )
    backend = OnnxRuntimeBackend(
        model_path="not-loaded-in-this-test.onnx",
        session=session,
        tokenizer=tokenizer,
    )

    vectors = backend.embed_texts(["candidate", "reference"])

    assert vectors == [[2.0, 0.0], [0.0, 1.0]]
    assert tokenizer.call_kwargs["padding"] is True
    assert tokenizer.call_kwargs["truncation"] is True
    assert tokenizer.call_kwargs["local_files_only"] if "local_files_only" in tokenizer.call_kwargs else True
    assert tokenizer.call_kwargs["return_tensors"] == "np"
    assert session.received_feed == {
        "input_ids": [[1, 2], [3, 0]],
        "attention_mask": [[1, 1], [1, 0]],
    }


def test_onnx_backend_accepts_sentence_embedding_output() -> None:
    backend = OnnxRuntimeBackend(
        model_path="not-loaded-in-this-test.onnx",
        session=_FakeSession(
            [[ [0.1, 0.2], [0.5, 0.7] ]],
            output_names=["sentence_embedding"],
        ),
        tokenizer=_FakeTokenizer(),
    )

    assert backend.embed_texts(["candidate", "reference"]) == [
        [0.1, 0.2],
        [0.5, 0.7],
    ]


def test_onnx_backend_empty_batch_does_not_load_optional_dependencies() -> None:
    backend = OnnxRuntimeBackend(model_path="does-not-exist.onnx")

    assert backend.embed_texts([]) == []


def test_onnx_backend_requires_a_local_model_file() -> None:
    backend = OnnxRuntimeBackend(
        model_path="missing-model.onnx",
        tokenizer=_FakeTokenizer(),
    )

    with pytest.raises(FileNotFoundError, match="ONNX model file"):
        backend.embed_texts(["candidate", "reference"])


def test_semantic_detector_tries_configured_fallbacks_in_order() -> None:
    fallback = OnnxRuntimeBackend(
        model_path="not-loaded-in-this-test.onnx",
        session=_FakeSession(
            [
                [
                    [[1.0, 0.0], [3.0, 0.0]],
                    [[0.0, 1.0], [0.0, 10.0]],
                ]
            ]
        ),
        tokenizer=_FakeTokenizer(),
    )
    detector = SemanticDetector(
        backend=_FailingBackend(),
        fallback_backends=[fallback],
        similarity_threshold=0.8,
    )

    similarity, contaminated = detector.compare("candidate", "reference")

    assert similarity == 0.0
    assert contaminated is False


def test_semantic_detector_uses_tfidf_after_all_backends_fail() -> None:
    detector = SemanticDetector(backend=_FailingBackend(), similarity_threshold=0.4)

    similarity, contaminated = detector.compare("alpha beta", "alpha gamma")

    assert similarity == 0.5
    assert contaminated is True


@pytest.mark.parametrize("threshold", [-0.1, 1.1, float("nan")])
def test_semantic_detector_rejects_invalid_similarity_threshold(
    threshold: float,
) -> None:
    with pytest.raises(ValueError, match="similarity_threshold"):
        SemanticDetector(similarity_threshold=threshold)


@pytest.mark.parametrize("max_length", [0, -1, True])
def test_onnx_backend_rejects_invalid_max_length(max_length: int) -> None:
    with pytest.raises(ValueError, match="max_length"):
        OnnxRuntimeBackend(model_path="unused.onnx", max_length=max_length)
