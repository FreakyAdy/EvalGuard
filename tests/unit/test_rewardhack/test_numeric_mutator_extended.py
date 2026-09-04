"""Extended unit tests for NumericEpsilonMutator and StringNormalizationMutator."""

from __future__ import annotations

from evalguard.rewardhack.mutations.numeric_mutator import (
    NumericEpsilonMutator,
    StringNormalizationMutator,
)


def test_numeric_epsilon_mutator_behavior() -> None:
    mutator = NumericEpsilonMutator()

    # Syntax error returns empty
    assert mutator.mutate("def broken(:\n  pass") == []

    # Numbers below 1e-6 are not perturbed
    code_tiny = "def test_tiny():\n    assert val == 1e-8\n"
    res_tiny = mutator.mutate(code_tiny)
    assert len(res_tiny) == 0

    # Numbers above 1e-6 are perturbed
    code_normal = "def test_float():\n    assert result == 3.14159\n"
    res_normal = mutator.mutate(code_normal)
    assert len(res_normal) == 1
    assert res_normal[0].strategy_name == "numeric_epsilon"
    assert "3.14159" in res_normal[0].mutated_code


def test_string_normalization_mutator_behavior() -> None:
    mutator = StringNormalizationMutator()

    # Syntax error returns empty
    assert mutator.mutate("invalid python ?? syntax") == []

    # String without trailing spaces is unmodified
    code_clean = 'def test_clean():\n    assert res == "hello"\n'
    assert mutator.mutate(code_clean) == []

    # String with trailing spaces is normalized
    code_trailing = 'def test_trailing():\n    assert res == "hello   "\n'
    res = mutator.mutate(code_trailing)
    assert len(res) == 1
    assert res[0].strategy_name == "string_normalization"
    assert "hello" in res[0].mutated_code
    assert "hello   " not in res[0].mutated_code
