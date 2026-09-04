# EvalGuard Architecture & Design Decisions

EvalGuard is built on three core design philosophies:
1. **Auditor, Not a Runner**: We never execute benchmarks directly or host leaderboards; we monitor and verify existing harness executions.
2. **Hermetic by Default, Graceful Degradation by Necessity**: System calls and kernel boundaries are audited with the highest available isolation primitive on the host.
3. **Wrap, Not Patch**: Integrating EvalGuard must require zero changes to a benchmark's internal code.

---

## Architectural Overview

```
+---------------------------------------------------------------------------------+
|                               External Benchmark Harness                        |
|                     (SWE-bench, Terminal-Bench, OpenEnv, Harbor)                |
+---------------------------------------------------------------------------------+
                                        │
                         [Wrap via HarnessAdapter]
                                        │
                                        ▼
+─────────────────────────────────────────────────────────────────────────────────+
|                           evalguard.adapters Layer                              |
|   - TaskContext Initialization                      - TaskResult Evaluation     |
|   - Boundary Profile Binding                        - Adapter Verification Suite|
+─────────────────────────────────────────────────────────────────────────────────+
                                        │
                                        ▼
+─────────────────────────────────────────────────────────────────────────────────+
|                           evalguard.sandbox Layer                               |
|                                                                                 |
|   Backends:             Monitoring:                       Snapshots:            |
|   - DockerBackend       - EbpfWatcher (openat/unlink)     - WorkspaceSnapshot   |
|   - PodmanBackend       - InotifyWatcher (fallback)         (SHA-256 Manifest)  |
|   - GVisorBackend       - ProcessMonitor (Ghost PIDs)     - SnapshotDiffRecord  |
|   - FirecrackerBackend  - Socket & Env Var Trackers                             |
+─────────────────────────────────────────────────────────────────────────────────+
                                        │
                      [BoundaryViolation & Artifact Stream]
                                        │
                                        ▼
+─────────────────────────────────────────────────────────────────────────────────+
|                           Integrity Analysis Engines                            |
|                                                                                 |
|   evalguard.rewardhack      evalguard.contamination     evalguard.testaudit     |
|   - Test Mutation Probes    - N-gram Sliding Windows    - Reference Runner      |
|   - AST Tamper Detector     - Sentence Transformers     - Statistical Anomalies |
|   - Trajectory Analyzer     - Timeline & Z-scores       - Cross-Harness Check   |
+─────────────────────────────────────────────────────────────────────────────────+
                                        │
                                        ▼
+─────────────────────────────────────────────────────────────────────────────────+
|                            evalguard.report Layer                               |
|   - Schema v1.0 (Pydantic v2 / JSON Schema)      - ReportDiffer                 |
|   - Rich Terminal Viewer                         - Exporters (MD, HTML, CSV,    |
|                                                               SARIF)            |
+─────────────────────────────────────────────────────────────────────────────────+
```

---

## Key Architectural Decisions

### 1. Why eBPF over inotify as Primary Isolation Watcher?

Traditional filesystem watchers (e.g. Linux `inotify`, Windows `ReadDirectoryChangesW`, macOS `FSEvents`) suffer from several critical shortcomings in adversarial agent benchmarking:

1. **Race Conditions & Dropped Events**: `inotify` queues have fixed buffer limits. When an agent unpacks an archive or creates thousands of files in parallel, inotify buffers overflow, silently dropping file creation events.
2. **Userspace Tampering**: Agents running as root inside a container can unmount, remount, or bypass userspace watchers via raw filesystem manipulations.
3. **Missing Syscall Context**: Inotify tells you *that* a file was written, but not *who* wrote it (`PID`, `UID`, process comm). In contrast, eBPF intercepts the kernel's `sys_enter_openat`, `sys_enter_unlinkat`, and `sys_enter_renameat2` syscalls inside the container's PID/cgroup namespace.
4. **Graceful Fallback**: Because eBPF requires a Linux kernel ≥ 4.18 and `CAP_SYS_ADMIN` privileges, EvalGuard automatically degrades to inotify watchers on macOS, Windows, and unprivileged container environments.

---

### 2. Why Content-Addressed (SHA-256) Snapshots Over Timestamp Diffing?

Many benchmark harnesses attempt to detect modified files using filesystem timestamps (`mtime`/`ctime`):

- **The Problem with Timestamps**: An agent that intentionally or accidentally executes `touch -r reference_file target_file` or resets file timestamps via `os.utime()` can completely hide unauthorized file edits from naive harness diffs. Furthermore, distributed filesystems and container volume mounts frequently suffer from clock skew.
- **EvalGuard's Approach**: Before a task runs, `WorkspaceSnapshot` walks the workspace directory tree and captures a cryptographic SHA-256 manifest of every file. After task teardown, an identical post-execution snapshot is computed and diffed.
- **Zero False Positives**: Because hashes are content-addressed, a file is only marked as modified if its actual bytes changed, regardless of timestamps or metadata manipulation.

---

### 3. Why the Adapter Layer "Wraps, Not Patches"?

The CUBE paper (March 2026) revealed that benchmark harnesses are severely fragmented across competing architectures (NeMo Gym, SWE-bench, Harbor, HAL, Terminal-Bench, OpenEnv).

- If EvalGuard required benchmark authors to adopt a new execution engine or rewrite their benchmark runners, adoption would stall.
- Instead, EvalGuard adopts the **Decorator / Adapter Pattern**. The `HarnessAdapter` wraps the existing harness execution inside a `with HarnessSandbox(...)` context.
- Harness maintainers only need to map their existing initialization and execution logic to four simple methods (`setup_task`, `run_task`, `teardown_task`, `reset_environment`).
- This design allows any harness to gain full EvalGuard compliance in **under 4 hours**, verified automatically by `evalguard adapter validate`.

---

### 4. Reward Hacking: Why Mutation Probing Beats Static Assertions

Agents are increasingly capable of finding zero-cost bypasses for visible test assertions (e.g., hardcoding literal return values for known inputs, or catching assertions and suppressing exceptions).

- **Static test verification fails** because it cannot distinguish between a model that computed `42` through general logic and one that returned `42` because `test_answer()` checked for `42`.
- **Dynamic Mutation Probing** solves this: EvalGuard generates semantically equivalent mutations of the test suite (inverting operand order in assertions, perturbing float epsilons, reordering independent statements, renaming local variables).
- If an agent genuinely generalized, its pass rate on mutated tests remains identical to the original tests. If it exploited syntactic fixture patterns, its mutation pass rate plummets, triggering an elevated reward hacking confidence score.
