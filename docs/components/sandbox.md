# evalguard.sandbox — Hermetic Isolation Layer

The `evalguard.sandbox` layer enforces and audits isolation boundaries across agent evaluation runs.

---

## Capabilities

1. **Multi-Backend Sandboxing**:
   - `DockerBackend`: Containerized execution with volume mounts and resource caps.
   - `PodmanBackend`: Daemonless, rootless container isolation.
   - `GVisorBackend`: Application kernel virtualization (`--runtime=runsc`).
   - `FirecrackerBackend`: Hardware-assisted microVM isolation via KVM.
   - `HostProcessBackend`: Cross-platform fallback for developer environments.
   - Automatic backend detection with graceful degradation.

2. **Filesystem Boundary Monitoring**:
   - **eBPF Syscall Interception**: On Linux kernels ≥ 4.18, attaches probes to `sys_enter_openat`, `sys_enter_unlinkat`, and `sys_enter_renameat2` to monitor all write operations in the target cgroup.
   - **Inotify / Watchdog Fallback**: Real-time cross-platform filesystem watcher for environments without eBPF.
   - Every write outside designated allowed paths triggers a `BoundaryViolationRecord`.

3. **Process Tree & Ghost Process Detection**:
   - Tracks the entire process tree using `psutil`.
   - Flags any process spawned during task execution that outlives the task boundary as a `ghost_process` violation.

4. **Cryptographic Workspace Manifests**:
   - Content-addressed (SHA-256) pre-task and post-task snapshots.
   - Diffs added, removed, and modified files with zero false positives from timestamp spoofing.

---

## Python API

```python
from evalguard.sandbox import HarnessSandbox, SandboxProfile

profile = SandboxProfile.from_yaml("my_bench.sandbox.yaml")

with HarnessSandbox(task_id="task_001", profile=profile, backend="auto") as sb:
    # Run agent task execution
    result = run_task()

violations = sb.get_violations()
diff = sb.get_snapshot_diff()
```
