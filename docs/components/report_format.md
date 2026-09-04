# EvalGuard Report Specification (v1.0)

EvalGuard publishes a versioned, machine-readable report format (`schemas/evalguard_report_v1.json`) for cross-lab reproducibility and citations.

---

## Schema Overview

The canonical report model `EvalGuardReport` contains:
- `schema_version`: `"1.0.0"`
- `report_id`: Unique audit identifier (`eg-xxxxxxxxxxxx`)
- `benchmark_id`: Name of audited benchmark
- `agent_id`: Model / agent identifier
- `harness_name`: Harness adapter name
- `summary`:
  - `total_tasks`
  - `agent_passed_tasks`
  - `clean_passed_tasks` (verified passing with zero violations, hacking, or contamination)
  - `boundary_violations_total`
  - `tasks_with_reward_hack`
  - `tasks_with_contamination`
  - `suspect_or_invalid_tests`
- `tasks`: Array of `TaskAuditRecord` entries detailing per-task findings.

---

## Exporters

- **Terminal**: `evalguard report view <file>`
- **Markdown**: `evalguard report export <file> -f markdown -o report.md`
- **HTML**: `evalguard report export <file> -f html -o report.html`
- **CSV**: `evalguard report export <file> -f csv -o report.csv`
- **SARIF**: `evalguard report export <file> -f sarif -o report.sarif`
