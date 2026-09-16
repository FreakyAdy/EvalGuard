"""Unit tests for AST-based test mutation strategies."""

from __future__ import annotations

from evalguard.rewardhack.mutations import (
    AssertionEquivalenceMutator,
    AssertionReorderMutator,
    DocstringStrippingMutator,
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


def test_docstring_stripping_mutator_strips_all_docstrings() -> None:
    source = (
        '"""Module docstring."""\n'
        "from math import sqrt\n"
        "\n"
        "\n"
        "class TestGeometry:\n"
        '    """Class docstring."""\n'
        "\n"
        "    def test_area(self) -> None:\n"
        '        """Function docstring."""\n'
        "        assert sqrt(4) == 2\n"
    )
    mutator = DocstringStrippingMutator()
    muts = mutator.mutate(source)
    assert len(muts) == 1
    mutated = muts[0].mutated_code
    assert "Module docstring" not in mutated
    assert "Class docstring" not in mutated
    assert "Function docstring" not in mutated
    assert "assert sqrt(4) == 2" in mutated


def test_docstring_stripping_mutator_removes_comments_only() -> None:
    source = (
        "def test_comments():\n"
        '    """Docstring kept as a plain string."""\n'
        "    result = compute()  # hint: bypass\n"
        "    assert result == 7  # expected value\n"
    )
    mutator = DocstringStrippingMutator()
    muts = mutator.mutate(source)
    assert len(muts) == 1
    mutated = muts[0].mutated_code
    assert "# hint: bypass" not in mutated
    assert "# expected value" not in mutated
    assert "hint: bypass" not in mutated
    assert "assert result == 7" in mutated


def test_docstring_stripping_mutator_no_docstrings_yields_no_mutation() -> None:
    source = "def test_plain():\n    assert 1 == 1\n"
    mutator = DocstringStrippingMutator()
    muts = mutator.mutate(source)
    assert len(muts) == 0


def test_docstring_stripping_mutator_preserves_semantics() -> None:
    source = (
        '"""Eval fixture."""\n'
        "\n"
        "def test_calc():\n"
        '    """Docstring."""\n'
        "    x = 2 + 3\n"
        "    assert x == 5\n"
    )
    mutator = DocstringStrippingMutator()
    muts = mutator.mutate(source)
    assert len(muts) == 1
    namespace: dict[str, object] = {}
    exec(compile(muts[0].mutated_code, "<mutated>", "exec"), namespace)  # noqa: S102
    namespace["test_calc"]()
