# EvalGuard Documentation

Welcome to **EvalGuard** — the open-source community infrastructure for auditing the integrity of AI agent benchmarks.

EvalGuard provides the critical missing verification layer between agent benchmark harnesses and published evaluation results. It audits hermetic sandboxing boundaries, unmasks reward hacking strategies, quantifies training data contamination, and validates test case integrity.

---

## The Philosophy: Auditor, Not a Runner

EvalGuard does not run evaluations or compete with benchmark platforms like SWE-bench, Terminal-Bench, or OpenEnv. Instead, it **audits** benchmark runs:

```
[Agent Execution] ──► [Harness Adapter] ──► [Harness Sandbox] ──► [EvalGuard Report]
                              │                     │
                    (OpenEnv / SWE-bench)   (eBPF / Snapshots)
```

By keeping EvalGuard strictly scoped as an auditor, benchmark maintainers can adopt it as an additive integrity layer without changing how they evaluate agents.

---

## Core Components

- [**Sandbox**](components/sandbox.md): Hermetic isolation, eBPF & inotify write interception, ghost process leak detection, SHA-256 workspace snapshotting.
- [**Reward Hacking**](components/rewardhack.md): AST-level test tampering detection, dynamic test mutation probing, trajectory anomaly analysis.
- [**Contamination**](components/contamination.md): N-gram lexical overlap, sentence-transformers semantic similarity, disclosure timeline audits, differential Z-score detection.
- [**Test Audit**](components/testaudit.md): Reference solver cross-validation, trivial non-solution permissiveness testing, universal pass/fail statistical anomalies, Markdown GitHub issue generation.
- [**Adapters**](adapters/writing_an_adapter.md): Standard "wrap, not patch" plugin layer with automated validation suite.
- [**Report Format**](components/report_format.md): Versioned schema v1.0, terminal viewer, side-by-side report diffs, and multi-format exporters (Markdown, HTML, CSV, SARIF).
