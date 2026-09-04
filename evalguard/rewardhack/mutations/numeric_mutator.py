"""Numeric epsilon perturbation and literal normalization mutation strategies."""

from __future__ import annotations

import ast
from uuid import uuid4

from evalguard.rewardhack.mutations.base import MutatedTest, MutationStrategy


class NumericEpsilonTransformer(ast.NodeTransformer):
    """Perturbs float literals in comparisons by an infinitesimal epsilon."""

    def __init__(self, epsilon: float = 1e-12) -> None:
        super().__init__()
        self.epsilon = epsilon
        self.mutated_count = 0

    def visit_Constant(self, node: ast.Constant) -> ast.Constant:
        if isinstance(node.value, float) and abs(node.value) > 1e-6:
            # Shift slightly without altering nominal tolerance
            new_val = node.value + self.epsilon
            self.mutated_count += 1
            return ast.copy_location(ast.Constant(value=new_val), node)
        return node


class NumericEpsilonMutator(MutationStrategy):
    """Perturbs floating-point comparison literals within standard numerical error bounds."""

    @classmethod
    def strategy_name(cls) -> str:
        return "numeric_epsilon"

    def mutate(self, test_source: str) -> list[MutatedTest]:
        try:
            tree = ast.parse(test_source)
        except SyntaxError:
            return []

        transformer = NumericEpsilonTransformer()
        new_tree = transformer.visit(tree)
        if transformer.mutated_count > 0:
            ast.fix_missing_locations(new_tree)
            return [
                MutatedTest(
                    mutation_id=f"epsilon_{uuid4().hex[:8]}",
                    strategy_name=self.strategy_name(),
                    original_code=test_source,
                    mutated_code=ast.unparse(new_tree),
                    description=f"Perturbed {transformer.mutated_count} float constant(s) by 1e-12 epsilon",
                )
            ]
        return []


class StringNormalizationMutator(MutationStrategy):
    """Normalizes string literals in tests (e.g. trailing newlines / spaces)."""

    @classmethod
    def strategy_name(cls) -> str:
        return "string_normalization"

    def mutate(self, test_source: str) -> list[MutatedTest]:
        try:
            tree = ast.parse(test_source)
        except SyntaxError:
            return []

        modified = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if node.value.endswith(" "):
                    node.value = node.value.rstrip(" ")
                    modified = True
                    break

        if modified:
            ast.fix_missing_locations(tree)
            return [
                MutatedTest(
                    mutation_id=f"str_norm_{uuid4().hex[:8]}",
                    strategy_name=self.strategy_name(),
                    original_code=test_source,
                    mutated_code=ast.unparse(tree),
                    description="Normalized whitespace in string literal assertion",
                )
            ]
        return []
