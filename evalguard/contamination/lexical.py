"""Lexical contamination detection using exact and fuzzy n-gram sliding windows."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass


def levenshtein_distance(s1: str, s2: str) -> int:
    """Compute Levenshtein edit distance between two strings with early exit for performance."""
    if s1 == s2:
        return 0
    if len(s1) < len(s2):
        s1, s2 = s2, s1

    if len(s2) == 0:
        return len(s1)

    previous_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def tokenize_code_or_text(text: str) -> list[str]:
    """Tokenize source code or prompt text into identifier and symbol tokens."""
    # Split on whitespace, identifiers, punctuation
    tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]*|[0-9]+|[^\s\w]", text.lower())
    return [t for t in tokens if t.strip()]


def extract_ngrams(tokens: Sequence[str], n: int) -> set[tuple[str, ...]]:
    """Extract set of n-grams of order n."""
    if len(tokens) < n:
        return set()
    return {tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1)}


@dataclass
class LexicalMatchResult:
    """Result of lexical contamination comparison."""

    n: int
    jaccard_similarity: float
    containment_score: float  # fraction of reference n-grams contained in candidate
    exact_match_count: int
    fuzzy_match_count: int
    longest_contiguous_tokens: int
    is_contaminated: bool


class LexicalDetector:
    """Detects text and code overlap using sliding window n-grams (3-gram to 8-gram)."""

    def __init__(
        self,
        n_gram_order: int = 6,
        containment_threshold: float = 0.50,
        jaccard_threshold: float = 0.35,
        enable_fuzzy: bool = True,
        max_fuzzy_distance: int = 2,
    ) -> None:
        if not (3 <= n_gram_order <= 8):
            raise ValueError(f"n_gram_order must be between 3 and 8, got {n_gram_order}")
        self.n_gram_order = n_gram_order
        self.containment_threshold = containment_threshold
        self.jaccard_threshold = jaccard_threshold
        self.enable_fuzzy = enable_fuzzy
        self.max_fuzzy_distance = max_fuzzy_distance

    def compare(self, candidate_text: str, reference_text: str) -> LexicalMatchResult:
        """Compare candidate text against a reference benchmark task or solution."""
        cand_tokens = tokenize_code_or_text(candidate_text)
        ref_tokens = tokenize_code_or_text(reference_text)

        cand_ngrams = extract_ngrams(cand_tokens, self.n_gram_order)
        ref_ngrams = extract_ngrams(ref_tokens, self.n_gram_order)

        if not ref_ngrams or not cand_ngrams:
            return LexicalMatchResult(
                n=self.n_gram_order,
                jaccard_similarity=0.0,
                containment_score=0.0,
                exact_match_count=0,
                fuzzy_match_count=0,
                longest_contiguous_tokens=0,
                is_contaminated=False,
            )

        # Exact matching
        common_ngrams = cand_ngrams & ref_ngrams
        exact_count = len(common_ngrams)

        # Jaccard similarity: |A & B| / |A | B|
        union_count = len(cand_ngrams | ref_ngrams)
        jaccard = (exact_count / union_count) if union_count > 0 else 0.0

        # Containment score: |A & B| / |B| (how much of reference is replicated)
        containment = (exact_count / len(ref_ngrams)) if ref_ngrams else 0.0

        # Fuzzy matching for remaining non-exact reference ngrams
        fuzzy_count = 0
        if self.enable_fuzzy and exact_count < len(ref_ngrams):
            unmatched_ref = ref_ngrams - common_ngrams
            cand_ngram_strings = {" ".join(ng): ng for ng in cand_ngrams}
            for ref_ng in list(unmatched_ref)[:200]:  # Cap to prevent combinatorial explosion
                ref_str = " ".join(ref_ng)
                for cand_str in cand_ngram_strings:
                    if abs(len(ref_str) - len(cand_str)) <= self.max_fuzzy_distance:
                        if levenshtein_distance(ref_str, cand_str) <= self.max_fuzzy_distance:
                            fuzzy_count += 1
                            break

        # Compute longest contiguous common token subsequence
        longest_subseq = self._longest_common_subsequence_length(cand_tokens, ref_tokens)

        is_contaminated = (
            containment >= self.containment_threshold
            or jaccard >= self.jaccard_threshold
            or longest_subseq >= 30  # 30 consecutive tokens copied verbatim
        )

        return LexicalMatchResult(
            n=self.n_gram_order,
            jaccard_similarity=round(jaccard, 4),
            containment_score=round(containment, 4),
            exact_match_count=exact_count,
            fuzzy_match_count=fuzzy_count,
            longest_contiguous_tokens=longest_subseq,
            is_contaminated=is_contaminated,
        )

    def _longest_common_subsequence_length(self, a: list[str], b: list[str]) -> int:
        """Find length of longest contiguous common substring."""
        if not a or not b:
            return 0
        # Rolling row dynamic programming for contiguous substring
        max_len = 0
        prev_row = [0] * (len(b) + 1)
        for _i, token_a in enumerate(a):
            curr_row = [0] * (len(b) + 1)
            for j, token_b in enumerate(b):
                if token_a == token_b:
                    curr_row[j + 1] = prev_row[j] + 1
                    if curr_row[j + 1] > max_len:
                        max_len = curr_row[j + 1]
            prev_row = curr_row
        return max_len
