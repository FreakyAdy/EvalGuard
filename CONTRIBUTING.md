# Contributing to EvalGuard

Thank you for contributing to EvalGuard! EvalGuard is production-grade infrastructure that agent evaluation harnesses and researchers depend on for benchmark integrity. We design our codebase to be welcoming, accessible, and maintainable from day one.

---

## The Contributor Ladder

We structure contributions into three distinct tiers so you can jump in at your comfort level:

### Level 1: Good First Issues (No Domain Expertise Required)
- **Implement a New Test Mutation Strategy**: Add a mutation strategy to `evalguard/rewardhack/mutations/` (e.g., dictionary key ordering mutation for Python dict assertions, boolean literal flipping, or list comprehension rewriting).
- **Add an Exporter**: Add support for new report export formats (e.g., JUnit XML, GitHub PR Check annotations, or Slack webhook summaries).
- **Enhance CLI Error Handling**: Improve user-facing guidance when optional dependency groups (e.g., `evalguard[semantic]`) are needed but missing.
- **Component tags**: `[rewardhack]`, `[report]`, `[cli]`

### Level 2: Intermediate Issues (Harness or Systems Knowledge)
- **Write a New Harness Adapter**: Add a first-party adapter in `evalguard/adapters/` for your favorite benchmark harness (e.g., Harbor, HAL, NeMo Gym). Maintainers can ship an adapter in under 4 hours using our `AdapterVerifier`.
- **Add a Benchmark Contamination Index**: Contribute pre-built token indices in `evalguard/contamination/indices/` for emerging agent benchmarks (e.g., SWE-bench Multimodal, WebArena).
- **Enhance Virtualization Backends**: Deepen the Firecracker microVM or gVisor `runsc` backends in `evalguard/sandbox/backends/`.
- **Component tags**: `[adapters]`, `[contamination]`, `[sandbox]`

### Level 3: Deep Systems & Research Issues
- **eBPF Kernel Probes**: Extend the eBPF tracer in `evalguard/sandbox/monitoring/ebpf_watcher.py` to trace raw TCP socket bind/connect calls and Unix domain socket IPC.
- **Cross-Harness Divergence Engine**: Implement statistical variance models for detecting environmental non-determinism across disparate container backends in `evalguard/testaudit/cross_harness.py`.
- **Trajectory Modeling**: Implement Markovian sequence anomaly detection in `evalguard/rewardhack/trajectory_analyzer.py` using non-contaminated human baselines.
- **Component tags**: `[sandbox]`, `[testaudit]`, `[rewardhack]`

---

## Development Setup

### 1. Prerequisites
- Python 3.10, 3.11, or 3.12
- Git
- Optional for sandboxing: Docker or Podman
- Optional for kernel tracing: Linux with root and `bcc`

### 2. Installation

```bash
git clone https://github.com/evalguard/evalguard.git
cd evalguard

# Install editable package with all development dependencies
pip install -e ".[all,dev]"
```

### 3. Code Standards & Tooling

We enforce strict quality gates in CI:

- **Linting & Formatting**: `ruff`
  ```bash
  ruff check evalguard/ tests/
  ruff format --check evalguard/ tests/
  ```
- **Static Typing**: `mypy --strict`
  ```bash
  mypy evalguard/
  ```
- **Testing**: `pytest` with coverage gate (minimum 80% line coverage)
  ```bash
  pytest tests/unit/ -v --cov=evalguard --cov-report=term-missing
  ```

---

## Writing a Harness Adapter

If you maintain a benchmark harness, adding EvalGuard support takes less than a day:

1. Subclass `evalguard.adapters.base.HarnessAdapter`.
2. Implement the four core methods:
   - `setup_task(task_id: str) -> TaskContext`
   - `run_task(agent: Any, task_id: str) -> TaskResult`
   - `teardown_task(task_id: str) -> None`
   - `reset_environment() -> None`
3. Validate your implementation using the built-in test suite:
   ```bash
   evalguard adapter validate my_package.adapter:MyAdapter
   ```
4. Submit a Pull Request with tests!

---

## Pull Request Checklist

Before submitting your PR, ensure:
- [ ] All unit tests pass (`pytest tests/unit/`).
- [ ] Coverage remains >= 80%.
- [ ] `ruff check evalguard/ tests/` reports no errors.
- [ ] `mypy evalguard/` passes with zero type errors.
- [ ] Any new public methods and classes have descriptive docstrings.
- [ ] Documentation in `docs/` is updated where appropriate.
