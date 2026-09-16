"""Test mutation probing strategies for reward hacking detection."""

from evalguard.rewardhack.mutations.assertion_mutator import (
    AssertionEquivalenceMutator,
    AssertionReorderMutator,
)
from evalguard.rewardhack.mutations.base import MutatedTest, MutationStrategy
from evalguard.rewardhack.mutations.numeric_mutator import (
    NumericEpsilonMutator,
    StringNormalizationMutator,
)
from evalguard.rewardhack.mutations.python_mutator import (
    DocstringStrippingMutator,
    PythonVariableMutator,
)

ALL_MUTATION_STRATEGIES: list[type[MutationStrategy]] = [
    AssertionEquivalenceMutator,
    AssertionReorderMutator,
    DocstringStrippingMutator,
    PythonVariableMutator,
    NumericEpsilonMutator,
    StringNormalizationMutator,
]

__all__ = [
    "ALL_MUTATION_STRATEGIES",
    "AssertionEquivalenceMutator",
    "AssertionReorderMutator",
    "DocstringStrippingMutator",
    "MutatedTest",
    "MutationStrategy",
    "NumericEpsilonMutator",
    "PythonVariableMutator",
    "StringNormalizationMutator",
]
