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
from evalguard.rewardhack.mutations.python_mutator import PythonVariableMutator

ALL_MUTATION_STRATEGIES: list[type[MutationStrategy]] = [
    AssertionEquivalenceMutator,
    AssertionReorderMutator,
    PythonVariableMutator,
    NumericEpsilonMutator,
    StringNormalizationMutator,
]

__all__ = [
    "ALL_MUTATION_STRATEGIES",
    "AssertionEquivalenceMutator",
    "AssertionReorderMutator",
    "MutatedTest",
    "MutationStrategy",
    "NumericEpsilonMutator",
    "PythonVariableMutator",
    "StringNormalizationMutator",
]
