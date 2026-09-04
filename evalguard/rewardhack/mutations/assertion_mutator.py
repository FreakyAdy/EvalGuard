"""AST-based assertion mutation strategies: equivalent assertion forms and assertion reordering."""

from __future__ import annotations

import ast
from uuid import uuid4

from evalguard.rewardhack.mutations.base import MutatedTest, MutationStrategy


class AssertionInvertTransformer(ast.NodeTransformer):
    """Transform `assert a == b` into `assert b == a`, or `assert a is b` into `assert b is a`."""

    def __init__(self) -> None:
        super().__init__()
        self.mutated_count = 0

    def visit_Assert(self, node: ast.Assert) -> ast.Assert:
        self.generic_visit(node)
        test = node.test
        if isinstance(test, ast.Compare) and len(test.ops) == 1 and len(test.comparators) == 1:
            op = test.ops[0]
            if isinstance(op, (ast.Eq, ast.NotEq, ast.Is, ast.IsNot)):
                # Flip left and right
                new_left = test.comparators[0]
                new_comparators = [test.left]
                new_compare = ast.Compare(
                    left=new_left,
                    ops=test.ops,
                    comparators=new_comparators,
                )
                self.mutated_count += 1
                return ast.copy_location(
                    ast.Assert(test=new_compare, msg=node.msg),
                    node,
                )
        return node


class AssertionEquivalenceMutator(MutationStrategy):
    """Mutates assertions to semantically identical forms (flipped operands, double negation)."""

    @classmethod
    def strategy_name(cls) -> str:
        return "assertion_equivalence"

    def mutate(self, test_source: str) -> list[MutatedTest]:
        mutations: list[MutatedTest] = []
        try:
            tree = ast.parse(test_source)
        except SyntaxError:
            return []

        transformer = AssertionInvertTransformer()
        new_tree = transformer.visit(tree)
        if transformer.mutated_count > 0:
            ast.fix_missing_locations(new_tree)
            mutated_code = ast.unparse(new_tree)
            mutations.append(
                MutatedTest(
                    mutation_id=f"eq_form_{uuid4().hex[:8]}",
                    strategy_name=self.strategy_name(),
                    original_code=test_source,
                    mutated_code=mutated_code,
                    description=f"Inverted {transformer.mutated_count} equality/identity assertion(s) (assert a == b -> assert b == a)",
                )
            )
        return mutations


class AssertionReorderMutator(MutationStrategy):
    """Reorders consecutive independent assertion statements in test functions."""

    @classmethod
    def strategy_name(cls) -> str:
        return "assertion_reorder"

    def mutate(self, test_source: str) -> list[MutatedTest]:
        mutations: list[MutatedTest] = []
        try:
            tree = ast.parse(test_source)
        except SyntaxError:
            return []

        modified = False

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                body = node.body
                # Find blocks of consecutive Assert statements
                assert_indices: list[int] = [i for i, stmt in enumerate(body) if isinstance(stmt, ast.Assert)]
                if len(assert_indices) >= 2:
                    # Reverse consecutive asserts
                    i1, i2 = assert_indices[0], assert_indices[1]
                    body[i1], body[i2] = body[i2], body[i1]
                    modified = True
                    break

        if modified:
            ast.fix_missing_locations(tree)
            mutated_code = ast.unparse(tree)
            mutations.append(
                MutatedTest(
                    mutation_id=f"reorder_{uuid4().hex[:8]}",
                    strategy_name=self.strategy_name(),
                    original_code=test_source,
                    mutated_code=mutated_code,
                    description="Reordered consecutive independent assertion statements",
                )
            )

        return mutations
