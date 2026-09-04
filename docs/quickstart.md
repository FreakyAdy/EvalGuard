# Quickstart Guide

Get up and running with EvalGuard in under 5 minutes.

---

## 1. Installation

Install via pip:

```bash
# Minimal installation
pip install evalguard

# With offline semantic embeddings
pip install evalguard[semantic]

# Full package
pip install evalguard[all]
```

---

## 2. Setting Up a Sandbox Profile

Sandbox profiles declare the hermetic boundaries for a benchmark task. Create `swe_bench.sandbox.yaml`:

```yaml
name: swebench-verified
task_workspace_root: ./workspace
allowed_write_paths:
  - ./workspace
  - /tmp/agent_scratch
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
timeout_seconds: 1200
```

---

## 3. Sandboxing an Evaluation Run

Wrap your existing agent execution inside the `HarnessSandbox` context manager:

```python
from evalguard.sandbox import HarnessSandbox, SandboxProfile

profile = SandboxProfile.from_yaml("swe_bench.sandbox.yaml")

with HarnessSandbox(task_id="task_001", profile=profile) as sb:
    # Run agent code or invoke benchmark runner
    result = run_agent("task_001")

violations = sb.get_violations()
diff = sb.get_snapshot_diff()

print(f"Recorded {len(violations)} boundary violation(s)")
print(f"Files modified by agent: {diff.modified_files}")
```

---

## 4. Detecting Reward Hacking

Audit whether an agent passed the tests by exploiting syntax or tampering with test fixtures:

```python
from evalguard.rewardhack import RewardHackAuditor

auditor = RewardHackAuditor(
    task=task,
    agent_result=result,
    test_sources={"test_core.py": test_code},
)
report = auditor.run(mutation_rounds=10)

print(f"Reward hack confidence: {report.confidence_score}")
print(f"Tamper events: {len(report.tamper_events)}")
```

---

## 5. Auditing Contamination via CLI

Check an agent's training data manifest against known benchmark disclosures:

```bash
evalguard contamination audit \
  --benchmark swebench-verified \
  --agent-corpus ./agent_training_manifest.json \
  --disclosure-date 2024-08-14 \
  --output ./contamination_report.json
```

---

## 6. Viewing and Exporting Reports

```bash
# Terminal summary viewer
evalguard report view ./audit_report.json

# Side-by-side report diff
evalguard report diff ./baseline_report.json ./candidate_report.json

# Export to HTML or SARIF
evalguard report export ./audit_report.json --format html --output ./audit.html
evalguard report export ./audit_report.json --format sarif --output ./results.sarif
```
