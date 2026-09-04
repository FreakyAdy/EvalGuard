# evalguard.testaudit — Test Case Integrity Auditor

The `evalguard.testaudit` module validates that benchmark test cases are themselves sound, non-permissive, and environment-independent.

---

## Capabilities

1. **Reference Solver Cross-Validation**:
   - Executes the benchmark test against the official canonical reference solution.
   - Flags tasks where the reference solution fails as `INVALID` — indicating a broken or outdated test case.

2. **Trivially Permissive Test Detection**:
   - Executes tests against trivial dummy solutions (e.g. empty output, `return None`, `return True`).
   - Flags tests that pass empty or trivial code as `SUSPECT` (too permissive).

3. **Population-Level Statistical Anomalies**:
   - Flags tasks that all agents universally pass (> 98%) or universally fail (> 98%) as degenerate tests.

4. **Cross-Harness Consistency Checks**:
   - Executes identical tasks across two harness backends and flags diverging results.

5. **GitHub Issue Generation**:
   - Automatically exports formatted Markdown reports ready to file as GitHub issues against the benchmark repository.
