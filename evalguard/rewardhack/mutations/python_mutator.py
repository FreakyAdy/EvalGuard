"""Variable rename and scope mutation strategy."""

from __future__ import annotations

import ast
from uuid import uuid4

from evalguard.rewardhack.mutations.base import MutatedTest, MutationStrategy


class VariableRenameTransformer(ast.NodeTransformer):
    """Safely renames local variables in test function scopes."""

    def __init__(self, rename_map: dict[str, str]) -> None:
        super().__init__()
        self.rename_map = rename_map
        self.mutated_count = 0

    def visit_Name(self, node: ast.Name) -> ast.Name:
        if node.id in self.rename_map:
            self.mutated_count += 1
            return ast.copy_location(ast.Name(id=self.rename_map[node.id], ctx=node.ctx), node)
        return node


class PythonVariableMutator(MutationStrategy):
    """Mutates variable names inside test functions while preserving exact semantics."""

    @classmethod
    def strategy_name(cls) -> str:
        return "variable_rename"

    def mutate(self, test_source: str) -> list[MutatedTest]:
        mutations: list[MutatedTest] = []
        try:
            tree = ast.parse(test_source)
        except SyntaxError:
            return []

        # Find local assignment targets to rename
        local_targets: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        # Don't rename dunders or builtins
                        if not target.id.startswith("__") and target.id not in ("self", "cls"):
                            local_targets.add(target.id)

        if not local_targets:
            return []

        # Pick up to 2 local variables to rename
        rename_map = {name: f"_eg_mut_{name}_{uuid4().hex[:4]}" for name in list(local_targets)[:2]}
        transformer = VariableRenameTransformer(rename_map)
        new_tree = transformer.visit(tree)

        if transformer.mutated_count > 0:
            ast.fix_missing_locations(new_tree)
            mutated_code = ast.unparse(new_tree)
            mutations.append(
                MutatedTest(
                    mutation_id=f"var_rename_{uuid4().hex[:8]}",
                    strategy_name=self.strategy_name(),
                    original_code=test_source,
                    mutated_code=mutated_code,
                    description=f"Renamed local test variables {list(rename_map.keys())} -> {list(rename_map.values())}",
                )
            )

        return mutations
