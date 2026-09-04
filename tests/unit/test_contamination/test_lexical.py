"""Unit tests for LexicalDetector n-gram overlap and fuzzy matching."""

from __future__ import annotations

from evalguard.contamination.lexical import (
    LexicalDetector,
    levenshtein_distance,
    tokenize_code_or_text,
)


def test_levenshtein_distance() -> None:
    assert levenshtein_distance("kitten", "sitting") == 3
    assert levenshtein_distance("assert", "assert") == 0
    assert levenshtein_distance("foo", "") == 3


def test_tokenize_code_or_text() -> None:
    tokens = tokenize_code_or_text("def solve(x: int) -> bool: return x == 10")
    assert "solve" in tokens
    assert "int" in tokens
    assert "10" in tokens


def test_lexical_detector_exact_contamination() -> None:
    detector = LexicalDetector(n_gram_order=4)
    ref = "def compute_area(width, height): return width * height"
    cand = "def compute_area(width, height): return width * height  # copied verbatim"

    res = detector.compare(candidate_text=cand, reference_text=ref)
    assert res.containment_score > 0.8
    assert res.is_contaminated is True


def test_lexical_detector_clean_dissimilar() -> None:
    detector = LexicalDetector(n_gram_order=6)
    ref = "def calculate_factorial(n): return math.factorial(n)"
    cand = "class NeuralNetwork(torch.nn.Module): def __init__(self): super().__init__()"

    res = detector.compare(candidate_text=cand, reference_text=ref)
    assert res.containment_score == 0.0
    assert res.is_contaminated is False
