# Architecture & Design Decisions

See the top-level [ARCHITECTURE.md](https://github.com/evalguard/evalguard/blob/main/ARCHITECTURE.md) for complete technical rationales on:
- eBPF vs inotify primary selection.
- Content-addressed (SHA-256) snapshots vs timestamp diffs.
- "Wrap, not patch" design for benchmark harness adapters.
- Dynamic test mutation probing vs static assertion verification.
