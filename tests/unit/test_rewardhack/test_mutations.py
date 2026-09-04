"""Unit tests for AST-based test mutation strategies."""

from __future__ import annotations

from evalguard.rewardhack.mutations import (
    AssertionEquivalenceMutator,
    AssertionReorderMutator,
    NumericEpsilonMutator,
    PythonVariableMutator,
)


def test_assertion_equivalence_mutator() -> None:
    source = "def test_val():\n    assert output == 100\n"
    mutator = AssertionEquivalenceMutator()
    muts = mutator.mutate(source)
    assert len(muts) == 1
    assert "100 == output" in muts[0].mutated_code


def test_assertion_reorder_mutator() -> None:
    source = "def test_two():\n    assert a == 1\n    assert b == 2\n"
    mutator = AssertionReorderMutator()
    muts = mutator.mutate(source)
    assert len(muts) == 1
    # Lines should be inverted
    lines = muts[0].mutated_code.strip().split("\n")
    assert "assert b == 2" in lines[1]
    assert "assert a == 1" in lines[2]


def test_python_variable_mutator() -> None:
    source = "def test_calc():\n    result = compute()\n    assert result == 42\n"
    mutator = PythonVariableMutator()
    muts = mutator.mutate(source)
    assert len(muts) == 1
    assert "_eg_mut_result" in muts[0].mutated_code


def test_numeric_epsilon_mutator() -> None:
    source = "def test_float():\n    val = 3.14159\n    assert val > 0\n"
    mutator = NumericEpsilonMutator()
    muts = mutator.mutate(source)
    assert len(muts) == 1
    assert "3.141590000001" in muts[0].mutated_code
