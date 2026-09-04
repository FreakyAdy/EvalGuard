"""Base classes and types for test mutation probing."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class MutatedTest:
    """A generated semantic mutation of a benchmark test."""

    mutation_id: str
    strategy_name: str
    original_code: str
    mutated_code: str
    description: str


class MutationStrategy(ABC):
    """Abstract strategy for generating semantically equivalent test mutations."""

    @classmethod
    @abstractmethod
    def strategy_name(cls) -> str:
        """Name of the mutation strategy."""
        ...

    @abstractmethod
    def mutate(self, test_source: str) -> list[MutatedTest]:
        """Generate mutations from test source code.

        Must preserve exact logical semantics while changing syntactic structure.
        """
        ...
