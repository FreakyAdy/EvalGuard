# Adapter Verification Test Suite

EvalGuard ships an automated adapter verification test suite to ensure that harness adapters conform to all lifecycle contracts before being deployed or merged.

---

## What the Suite Validates

1. **`setup_task` Contract**:
   - Returns an instance of `TaskContext`.
   - `TaskContext.workspace_root` points to a valid, existing directory on disk.

2. **`run_task` Contract**:
   - Accepts a callable or command agent.
   - Returns a valid `TaskResult`.
   - `TaskResult.passed` is strictly a boolean.
   - `TaskResult.duration_seconds` is a non-negative float.

3. **`teardown_task` Contract**:
   - Executes cleanly without unhandled exceptions.

4. **`reset_environment` Contract**:
   - Resets state without leaking lingering variables or processes.

5. **`run_task_with_audit` Contract**:
   - Wraps task execution seamlessly inside `HarnessSandbox`.
   - Captures boundary violations and workspace snapshot diffs.
