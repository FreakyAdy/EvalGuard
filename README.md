# 🛡️ EvalGuard

**Benchmark Integrity Infrastructure for Agent Evaluations**

[![CI](https://github.com/evalguard/evalguard/actions/workflows/ci.yml/badge.svg)](https://github.com/evalguard/evalguard/actions)
[![PyPI version](https://img.shields.io/pypi/v/evalguard.svg)](https://pypi.org/project/evalguard/)
[![Python versions](https://img.shields.io/pypi/pyversions/evalguard.svg)](https://pypi.org/project/evalguard/)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Coverage](https://img.shields.io/badge/coverage-85%25-brightgreen.svg)](https://github.com/evalguard/evalguard)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Type Checking: mypy strict](https://img.shields.io/badge/mypy-strict-blue.svg)](https://mypy.readthedocs.io/)

EvalGuard is a production-grade, community-adopted open-source framework for auditing the integrity of AI agent benchmarks. It is an **auditor, not a runner** — it monitors, verifies, and hermetically audits agent evaluations across existing harnesses without replacing them.

---

## The Crisis in Agent Benchmarking

Recent empirical studies across SWE-bench Verified, Terminal-Bench, and CUBE (March 2026) have exposed severe structural failure modes in agent evaluations:

1. **Reward hacking without task completion**: Agents pass visible assertions by hardcoding responses, inverting assertion tests, or patching test files in-place rather than solving the underlying task.
2. **Cross-task state leakage**: Non-hermetic task resets leave behind lingering daemons, mounted volumes, environment variables, network sockets, and shared memory segments that silently corrupt subsequent benchmark tasks.
3. **Training data contamination**: Models trained or fine-tuned on benchmark fixtures, prompts, or disclosed PRs exhibit artificial performance spikes that do not reflect genuine generalization.
4. **Flawed test case integrity**: A non-trivial fraction of benchmark tests reject correct reference solutions, accept trivial empty implementations, or exhibit extreme statistical bimodality.
5. **Infrastructure fragmentation**: Benchmark harnesses (SWE-bench, Terminal-Bench, OpenEnv, Harbor, HAL, NeMo Gym) have incompatible isolation and monitoring interfaces.

---

## Key Components

| Component | Module | Key Capabilities |
| :--- | :--- | :--- |
| **Hermetic Isolation** | `evalguard.sandbox` | Container/microVM boundary monitoring (`Docker`, `Podman`, `gVisor`, `Firecracker`), eBPF & inotify write interception, ghost process leak detection, SHA-256 workspace snapshot manifests. |
| **Reward Hacking Detector** | `evalguard.rewardhack` | Dynamic test mutation probing (variable rename, assertion inversion, assertion reordering, numeric epsilon perturbation), AST-level static test tampering detection (`conftest.py`, `sys.path`, `mock` interception), trajectory anomaly analysis. |
| **Contamination Auditor** | `evalguard.contamination` | Exact & fuzzy n-gram sliding window matching (3 to 8-grams), offline semantic embedding similarity (`sentence-transformers`), pre-training cutoff vs disclosure timeline auditing, cross-agent differential Z-score analysis. |
| **Test Case Integrity** | `evalguard.testaudit` | Reference solver cross-validation, trivial non-solution permissiveness testing, population-level statistical anomaly detection (>98% universal pass/fail), cross-harness divergence verification, Markdown GitHub issue generation. |
| **Harness Adapter Layer** | `evalguard.adapters` | Stable "wrap, not patch" plugin interface for OpenEnv, Terminal-Bench, SWE-bench, and generic subprocesses. Built-in `AdapterVerifier` test suite and `pytest-evalguard-adapter` plugin. |
| **Standard Audit Reports** | `evalguard.report` | Pydantic v2 / JSON Schema v1.0 standard report specification (`evalguard_report_v1.json`), Rich terminal viewer, side-by-side report diffing, and exporters to Markdown, HTML, CSV, and SARIF. |

---

## Quickstart

### Installation

```bash
# Minimal install (sandbox, adapters, CLI, lexical contamination, test audit)
pip install evalguard

# With offline semantic embedding models
pip install evalguard[semantic]

# Full suite with optional LLM API backends
pip install evalguard[all]
```

### 1. Hermetic Task Sandboxing

```python
from evalguard.sandbox import HarnessSandbox, SandboxProfile

profile = SandboxProfile.from_yaml("sandbox_profiles/swebench_verified.sandbox.yaml")

with HarnessSandbox(task_id="task_001", profile=profile) as sb:
    # Run any existing agent evaluation
    result = run_agent("task_001")

# Inspect violations and cryptographic workspace diff
violations = sb.get_violations()
diff = sb.get_snapshot_diff()

print(f"Violations: {len(violations)}")
print(f"Modified files: {diff.modified_files}")
```

### 2. Reward Hacking Audit

```python
from evalguard.rewardhack import RewardHackAuditor

auditor = RewardHackAuditor(
    task=task,
    agent_result=result,
    test_sources={"test_solution.py": test_code},
)
report = auditor.run(mutation_rounds=10)

print(f"Confidence score: {report.confidence_score}")  # 0.0 = clean, 1.0 = definite hack
print(f"Tamper events: {report.tamper_events}")
print(f"Mutation pass rate: {report.mutation_pass_rate:.1%}")
```

### 3. Contamination Auditing via CLI

```bash
evalguard contamination audit \
  --benchmark swebench-verified \
  --agent-corpus ./agent_training_manifest.json \
  --disclosure-date 2024-08-14 \
  --output ./contamination_report.json
```

### 4. Viewing and Diffing Reports

```bash
# View human-readable terminal report
evalguard report view ./audit_report.json

# Compare two evaluations to detect regressions or leaks
evalguard report diff ./baseline_report.json ./candidate_report.json

# Export to GitHub-flavored Markdown, HTML, CSV, or SARIF
evalguard report export ./audit_report.json --format html --output ./audit.html
evalguard report export ./audit_report.json --format sarif --output ./results.sarif
```

---

## Adapter Integration: Bring Your Own Harness in Under 4 Hours

EvalGuard does not ask you to rewrite your benchmark. Simply inherit from `HarnessAdapter`:

```python
from evalguard.adapters import HarnessAdapter, TaskContext, TaskResult

class MyCustomHarnessAdapter(HarnessAdapter):
    def setup_task(self, task_id: str) -> TaskContext:
        # Create workspace directory and return TaskContext
        ...

    def run_task(self, agent: Any, task_id: str) -> TaskResult:
        # Execute your existing benchmark run
        ...

    def teardown_task(self, task_id: str) -> None:
        # Cleanup task resources
        ...

    def reset_environment(self) -> None:
        # Global environment reset
        ...
```

Verify your adapter against the EvalGuard contract suite:

```bash
evalguard adapter validate my_harness.adapter:MyCustomHarnessAdapter
```

Or using pytest:

```python
def test_my_adapter(evalguard_verifier):
    evalguard_verifier(MyCustomHarnessAdapter())
```

---

## Sandbox Profiles

Maintainers ship a `*.sandbox.yaml` profile alongside their benchmark repository declaring permissions:

```yaml
name: swebench-verified
task_workspace_root: ./workspace
allowed_write_paths:
  - ./workspace
  - /tmp/scratch
denied_write_paths:
  - /etc
  - /usr
  - ~/.ssh
allowed_env_vars:
  - PATH
  - HOME
  - PYTHONPATH
allow_outbound_network: false
max_memory_mb: 8192
timeout_seconds: 1800
prevent_ghost_processes: true
track_shared_memory: true
```

---

## Contributing

We welcome contributions at all experience levels! See [CONTRIBUTING.md](CONTRIBUTING.md) for our contribution ladder:
- **Good First Issues**: Add a new mutation strategy, add an exporter format, or improve error messages.
- **Intermediate**: Write a new harness adapter or benchmark contamination index.
- **Deep Systems**: eBPF kernel probes, gVisor/Firecracker optimizations, and cross-harness statistical algorithms.

---

## Architecture & Design Decisions

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed technical justifications on:
- Why **eBPF** is used over inotify as primary for Linux kernel-level interception.
- Why **content-addressed (SHA-256) snapshots** replace timestamp diffing to prevent clock skew attacks.
- Why **wrapping rather than patching** guarantees rapid adoption across fragmented harnesses.

---

## License

EvalGuard is released under the [Apache 2.0 License](LICENSE).
