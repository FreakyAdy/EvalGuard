# Writing a Custom Harness Adapter

Any benchmark harness maintainer who has never seen EvalGuard before can integrate EvalGuard in **under 4 hours**.

---

## 1. The Interface

Subclass `evalguard.adapters.base.HarnessAdapter`:

```python
from evalguard.adapters import HarnessAdapter, TaskContext, TaskResult

class MyHarnessAdapter(HarnessAdapter):
    def __init__(self):
        super().__init__(name="my-harness")

    def setup_task(self, task_id: str) -> TaskContext:
        """Create workspace and return task context."""
        ws = f"./workspaces/{task_id}"
        os.makedirs(ws, exist_ok=True)
        return TaskContext(task_id=task_id, workspace_root=ws)

    def run_task(self, agent: Any, task_id: str) -> TaskResult:
        """Run agent using your native evaluation loop."""
        start = time.time()
        passed, output = my_native_eval(agent, task_id)
        return TaskResult(
            task_id=task_id,
            passed=passed,
            duration_seconds=time.time() - start,
            output=output,
        )

    def teardown_task(self, task_id: str) -> None:
        """Cleanup any task-specific state."""
        pass

    def reset_environment(self) -> None:
        """Reset environment between full evaluation runs."""
        pass
```

---

## 2. Testing Your Adapter

Validate your adapter implementation against the EvalGuard contract suite:

```bash
evalguard adapter validate my_package.adapters:MyHarnessAdapter
```

Or write a pytest test with the `evalguard_verifier` fixture:

```python
def test_my_adapter_contract(evalguard_verifier):
    adapter = MyHarnessAdapter()
    evalguard_verifier(adapter)
```
