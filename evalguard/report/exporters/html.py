"""Self-contained interactive HTML reports for EvalGuard audits."""

from __future__ import annotations

import html
import json
from typing import Any

from evalguard.report.schema import EvalGuardReport, TaskAuditRecord


def _text(value: Any) -> str:
    """HTML-escape a value for text or a quoted attribute."""
    return html.escape(str(value), quote=True)


def _list_items(values: list[str], empty_message: str = "None") -> str:
    """Render an escaped list of strings."""
    if not values:
        return f'<p class="muted">{_text(empty_message)}</p>'
    return "<ul>" + "".join(f"<li>{_text(value)}</li>" for value in values) + "</ul>"


def _task_details(task: TaskAuditRecord) -> str:
    """Render expandable, escaped task evidence."""
    sections: list[str] = []

    if task.violations:
        violation_rows = []
        for violation in task.violations:
            severity = str(violation.severity).lower()
            violation_rows.append(
                "<tr>"
                f'<td><span class="badge severity-{_text(severity)}">{_text(violation.severity)}</span></td>'
                f"<td>{_text(violation.violation_type.value)}</td>"
                f"<td><code>{_text(violation.target)}</code></td>"
                f"<td>{_text(violation.detail)}</td>"
                f"<td>{_text(violation.timestamp.isoformat())}</td>"
                "</tr>"
            )
        sections.append(
            "<section><h3>Boundary violations</h3>"
            '<div class="table-scroll"><table class="detail-table"><thead><tr>'
            "<th>Severity</th><th>Type</th><th>Target</th><th>Detail</th><th>Timestamp</th>"
            "</tr></thead><tbody>" + "".join(violation_rows) + "</tbody></table></div></section>"
        )
    else:
        sections.append(
            '<section><h3>Boundary violations</h3><p class="muted">None recorded.</p></section>'
        )

    if task.snapshot_diff:
        diff = task.snapshot_diff
        sections.append(
            "<section><h3>Workspace snapshot</h3>"
            f"<p>Files before: <strong>{diff.total_files_before}</strong> · "
            f"files after: <strong>{diff.total_files_after}</strong></p>"
            '<div class="evidence-grid">'
            f"<div><h4>Added ({len(diff.added_files)})</h4>{_list_items(diff.added_files)}</div>"
            f"<div><h4>Removed ({len(diff.removed_files)})</h4>{_list_items(diff.removed_files)}</div>"
            f"<div><h4>Modified ({len(diff.modified_files)})</h4>{_list_items(diff.modified_files)}</div>"
            "</div></section>"
        )

    if task.reward_hack:
        reward = task.reward_hack
        events = []
        for event in reward.tamper_events:
            snippet = ""
            if event.code_snippet:
                snippet = f"<pre><code>{_text(event.code_snippet)}</code></pre>"
            line = f":{event.line_number}" if event.line_number is not None else ""
            events.append(
                '<article class="evidence-item">'
                f"<h4>{_text(event.tamper_type.value)}</h4>"
                f"<p><code>{_text(event.file_path)}{_text(line)}</code></p>"
                f"<p>{_text(event.description)}</p>{snippet}</article>"
            )
        probes = []
        for probe in reward.mutation_probes:
            probes.append(
                "<li>"
                f"<strong>{_text(probe.strategy)}</strong>: "
                f"{'passed' if probe.mutated_passed else 'failed'} after mutation. "
                f"{_text(probe.diff_summary)}</li>"
            )
        trajectory = ""
        if reward.trajectory:
            trajectory = (
                "<p>Trajectory: "
                f"{reward.trajectory.edit_count} edits; "
                f"{reward.trajectory.test_runs_before_success} test runs before success; "
                f"first-attempt success: {reward.trajectory.first_attempt_success}.</p>"
                f"{_list_items(reward.trajectory.notes, 'No trajectory notes.')}"
            )
        sections.append(
            "<section><h3>Reward-hacking evidence</h3>"
            f"<p>Confidence score: <strong>{reward.confidence_score:.2f}</strong> · "
            f"Mutation probes passed: {reward.mutation_rounds_passed}/"
            f"{reward.mutation_rounds_total}</p>"
            + ("".join(events) if events else '<p class="muted">No tamper events recorded.</p>')
            + ("<h4>Mutation probes</h4><ul>" + "".join(probes) + "</ul>" if probes else "")
            + trajectory
            + "</section>"
        )

    if task.contamination_flags:
        contamination_items = []
        for flag in task.contamination_flags:
            state = "FLAGGED" if flag.is_contaminated else "CLEAN"
            contamination_items.append(
                "<li>"
                f"<strong>{_text(flag.method.value)} · {state}</strong> "
                f"(score {_text(flag.score)}, threshold {_text(flag.threshold)}): "
                f"{_text(flag.details)}"
                + (
                    f" Matched reference: <code>{_text(flag.matched_reference)}</code>."
                    if flag.matched_reference
                    else ""
                )
                + "</li>"
            )
        contamination_html = "<ul>" + "".join(contamination_items) + "</ul>"
    else:
        contamination_html = '<p class="muted">No contamination flags recorded.</p>'
    sections.append(f"<section><h3>Contamination</h3>{contamination_html}</section>")

    if task.test_integrity:
        integrity = task.test_integrity
        sections.append(
            "<section><h3>Test integrity</h3>"
            f"<p>Status: <strong>{_text(integrity.status.value)}</strong>"
            + (
                f" · Reference solver passed: <strong>{integrity.reference_solver_passed}</strong>"
                if integrity.reference_solver_passed is not None
                else ""
            )
            + (
                f" · Universal pass rate: <strong>{integrity.universal_pass_rate:.1%}</strong>"
                if integrity.universal_pass_rate is not None
                else ""
            )
            + "</p>"
            + _list_items(integrity.evidence, "No integrity evidence recorded.")
            + "</section>"
        )
    else:
        sections.append(
            '<section><h3>Test integrity</h3><p class="muted">No test-integrity audit recorded.</p></section>'
        )

    return "".join(sections)


def _task_search_text(task: TaskAuditRecord) -> str:
    """Build a searchable string that includes hidden, expandable evidence."""
    values = [task.task_id, "pass" if task.agent_passed else "fail"]
    values.extend(
        f"{v.severity} {v.violation_type.value} {v.target} {v.detail}" for v in task.violations
    )
    if task.reward_hack:
        values.extend(
            f"{event.file_path} {event.description} {event.code_snippet or ''}"
            for event in task.reward_hack.tamper_events
        )
    values.extend(flag.details for flag in task.contamination_flags)
    if task.test_integrity:
        values.extend(task.test_integrity.evidence)
    if task.snapshot_diff:
        values.extend(
            task.snapshot_diff.added_files
            + task.snapshot_diff.removed_files
            + task.snapshot_diff.modified_files
        )
    return " ".join(values).casefold()


def _task_row(task: TaskAuditRecord, index: int) -> str:
    pass_badge = (
        '<span class="badge pass">PASS</span>'
        if task.agent_passed
        else '<span class="badge fail">FAIL</span>'
    )
    if task.violations:
        boundary_badge = f'<span class="badge warn">{len(task.violations)} violation(s)</span>'
    else:
        boundary_badge = '<span class="badge clean">Hermetic</span>'

    hack_score = task.reward_hack.confidence_score if task.reward_hack else 0.0
    hack_class = "fail" if hack_score >= 0.7 else ("warn" if hack_score >= 0.3 else "clean")
    hack_badge = f'<span class="badge {hack_class}">{hack_score:.2f}</span>'

    contaminated = any(flag.is_contaminated for flag in task.contamination_flags)
    contamination_badge = (
        '<span class="badge warn">Flagged</span>'
        if contaminated
        else '<span class="badge clean">Clean</span>'
    )

    integrity_status = task.test_integrity.status.value if task.test_integrity else "PASS"
    integrity_class = (
        "fail"
        if integrity_status == "INVALID"
        else ("warn" if integrity_status == "SUSPECT" else "clean")
    )
    integrity_badge = f'<span class="badge {integrity_class}">{_text(integrity_status)}</span>'
    severities = " ".join(sorted({v.severity.lower() for v in task.violations})) or "none"
    details = _task_details(task)

    return (
        f'<tr class="task-row" data-row-id="{index}" '
        f'data-severity="{_text(severities)}" '
        f'data-search="{_text(_task_search_text(task))}">'
        f"<td><code>{_text(task.task_id)}</code></td>"
        f"<td>{pass_badge}</td>"
        f"<td>{boundary_badge}</td>"
        f"<td>{hack_badge}</td>"
        f"<td>{contamination_badge}</td>"
        f"<td>{integrity_badge}</td>"
        f'<td class="duration">{task.duration_seconds:.2f}s</td>'
        "</tr>"
        f'<tr class="detail-row" data-parent="{index}"><td colspan="7">'
        f'<details><summary>Inspect task evidence</summary><div class="details-content">{details}</div></details>'
        "</td></tr>"
    )


_CSS = r"""
:root { color-scheme: dark; --bg:#0d1117; --surface:#161b22; --surface-alt:#21262d; --border:#30363d; --text:#c9d1d9; --muted:#8b949e; --accent:#58a6ff; --green:#3fb950; --red:#f85149; --yellow:#d29922; }
:root[data-theme="light"] { color-scheme: light; --bg:#f6f8fa; --surface:#ffffff; --surface-alt:#eaeef2; --border:#d0d7de; --text:#1f2328; --muted:#59636e; --accent:#0969da; --green:#1a7f37; --red:#cf222e; --yellow:#9a6700; }
* { box-sizing:border-box; }
body { font-family:system-ui,-apple-system,"Segoe UI",sans-serif; background:var(--bg); color:var(--text); margin:0; padding:clamp(1rem,3vw,2.5rem); line-height:1.5; }
.container { max-width:1280px; margin:0 auto; }
header { border-bottom:1px solid var(--border); padding-bottom:1.5rem; margin-bottom:1.5rem; }
.header-row { display:flex; flex-wrap:wrap; justify-content:space-between; align-items:flex-start; gap:1rem; }
h1 { margin:.2rem 0 .6rem; font-size:clamp(1.6rem,3vw,2.4rem); }
h2 { margin-top:2rem; }
h3 { margin:.6rem 0; font-size:1.05rem; }
h4 { margin:.5rem 0; }
.meta,.muted { color:var(--muted); font-size:.92rem; }
code,pre { font-family:ui-monospace,SFMono-Regular,Consolas,monospace; overflow-wrap:anywhere; }
code { color:var(--accent); }
.grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:1rem; margin:1.4rem 0 2rem; }
.card { background:var(--surface); border:1px solid var(--border); border-radius:10px; padding:1.1rem; }
.card-title { color:var(--muted); font-size:.78rem; letter-spacing:.06em; text-transform:uppercase; }
.card-val { font-size:1.8rem; font-weight:750; margin-top:.35rem; }
.toolbar { display:flex; flex-wrap:wrap; gap:.75rem; align-items:end; margin:1rem 0; }
.field { display:flex; flex-direction:column; gap:.25rem; min-width:min(100%,240px); flex:1; }
label { color:var(--muted); font-size:.85rem; }
input,select,button { font:inherit; border:1px solid var(--border); border-radius:7px; padding:.6rem .75rem; color:var(--text); background:var(--surface); }
button { cursor:pointer; }
button:hover { border-color:var(--accent); }
button:focus-visible,input:focus-visible,select:focus-visible,summary:focus-visible { outline:2px solid var(--accent); outline-offset:2px; }
.controls { display:flex; flex-wrap:wrap; gap:.5rem; }
.table-scroll { overflow-x:auto; border:1px solid var(--border); border-radius:9px; background:var(--surface); }
table { width:100%; border-collapse:collapse; min-width:850px; }
th,td { padding:.75rem .9rem; text-align:left; vertical-align:top; border-bottom:1px solid var(--border); }
th { background:var(--surface-alt); color:var(--muted); font-size:.78rem; letter-spacing:.05em; text-transform:uppercase; white-space:nowrap; }
.task-row:hover { background:color-mix(in srgb,var(--accent) 6%,var(--surface)); }
.detail-row[hidden],.task-row[hidden],#no-results[hidden] { display:none; }
.detail-row td { background:var(--surface); padding:0 1rem 1rem; }
details summary { cursor:pointer; color:var(--accent); padding:.8rem 0; }
.details-content { display:grid; gap:1rem; }
.details-content section { border:1px solid var(--border); border-radius:8px; padding:.8rem; }
.detail-table { min-width:750px; }
.detail-table td { font-size:.9rem; }
.evidence-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:.75rem; }
.evidence-grid>div,.evidence-item { border:1px solid var(--border); border-radius:7px; padding:.65rem; min-width:0; }
pre { background:var(--surface-alt); border-radius:6px; padding:.75rem; white-space:pre-wrap; }
.badge { display:inline-block; padding:.15rem .45rem; border-radius:5px; font-size:.75rem; font-weight:700; white-space:nowrap; }
.badge.pass,.badge.clean { background:color-mix(in srgb,var(--green) 15%,transparent); color:var(--green); }
.badge.fail { background:color-mix(in srgb,var(--red) 15%,transparent); color:var(--red); }
.badge.warn { background:color-mix(in srgb,var(--yellow) 16%,transparent); color:var(--yellow); }
.severity-critical { background:color-mix(in srgb,var(--red) 16%,transparent); color:var(--red); }
.severity-high { background:color-mix(in srgb,var(--red) 12%,transparent); color:var(--red); }
.severity-medium { background:color-mix(in srgb,var(--yellow) 16%,transparent); color:var(--yellow); }
.severity-low { background:color-mix(in srgb,var(--green) 15%,transparent); color:var(--green); }
#result-count { color:var(--muted); font-size:.9rem; margin:.75rem 0; }
footer { color:var(--muted); font-size:.85rem; padding:1.5rem 0; }
@media (prefers-reduced-motion:reduce) { *,*::before,*::after { scroll-behavior:auto!important; transition:none!important; } }
"""


_SCRIPT = r"""
(() => {
  "use strict";
  const reportNode = document.getElementById("report-data");
  const report = JSON.parse(reportNode.textContent);
  const searchInput = document.getElementById("task-search");
  const severitySelect = document.getElementById("severity-filter");
  const rows = Array.from(document.querySelectorAll(".task-row"));
  const details = Array.from(document.querySelectorAll(".detail-row"));
  const noResults = document.getElementById("no-results");
  const resultCount = document.getElementById("result-count");
  const themeButton = document.getElementById("theme-toggle");

  function applyFilters() {
    const query = searchInput.value.trim().toLocaleLowerCase();
    const severity = severitySelect.value;
    let visible = 0;
    for (const row of rows) {
      const matchesQuery = !query || row.dataset.search.includes(query);
      const severities = row.dataset.severity.split(" ");
      const matchesSeverity = severity === "all" || severities.includes(severity);
      const show = matchesQuery && matchesSeverity;
      row.hidden = !show;
      const detail = details.find(item => item.dataset.parent === row.dataset.rowId);
      if (detail) detail.hidden = !show;
      if (show) visible += 1;
    }
    resultCount.textContent = "Showing " + visible + " of " + rows.length + " tasks";
    noResults.hidden = visible !== 0;
  }

  function downloadFile(filename, content, mimeType) {
    const blob = new Blob([content], {type: mimeType});
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function csvCell(value) {
    let text = String(value ?? "");
    if (typeof value === "string" && /^[\t\r ]*[=+\-@]/.test(text)) {
      text = "'" + text;
    }
    return '"' + text.replace(/"/g, '""') + '"';
  }

  function exportCsv() {
    const columns = [
      ["task_id", task => task.task_id],
      ["agent_passed", task => task.agent_passed],
      ["duration_seconds", task => task.duration_seconds],
      ["boundary_violation_count", task => task.violations.length],
      ["boundary_violation_severities", task => task.violations.map(v => v.severity).join("; ")],
      ["boundary_violation_types", task => task.violations.map(v => v.violation_type).join("; ")],
      ["reward_hack_score", task => task.reward_hack ? task.reward_hack.confidence_score : 0],
      ["contaminated", task => task.contamination_flags.some(flag => flag.is_contaminated)],
      ["test_integrity_status", task => task.test_integrity ? task.test_integrity.status : "PASS"]
    ];
    const lines = [
      columns.map(([name]) => csvCell(name)).join(","),
      ...report.tasks.map(task => columns.map(([, accessor]) => csvCell(accessor(task))).join(","))
    ];
    downloadFile("evalguard-report.csv", "\uFEFF" + lines.join("\r\n"), "text/csv;charset=utf-8");
  }

  document.getElementById("export-json").addEventListener("click", () => {
    downloadFile(
      "evalguard-report.json",
      JSON.stringify(report, null, 2),
      "application/json;charset=utf-8"
    );
  });
  document.getElementById("export-csv").addEventListener("click", exportCsv);
  searchInput.addEventListener("input", applyFilters);
  severitySelect.addEventListener("change", applyFilters);
  themeButton.addEventListener("click", () => {
    const root = document.documentElement;
    const next = root.dataset.theme === "light" ? "dark" : "light";
    root.dataset.theme = next;
    themeButton.setAttribute("aria-pressed", String(next === "light"));
    themeButton.textContent = next === "light" ? "Switch to dark mode" : "Switch to light mode";
  });

  applyFilters();
})();
"""


class HtmlExporter:
    """Export an EvalGuardReport to a self-contained, interactive HTML file."""

    @classmethod
    def export(cls, report: EvalGuardReport) -> str:
        """Render a standalone report with searchable evidence and offline exports."""
        summary = report.summary
        clean_pct = (
            f"{summary.clean_passed_tasks / summary.total_tasks * 100:.1f}%"
            if summary.total_tasks
            else "0%"
        )
        raw_pct = (
            f"{summary.agent_passed_tasks / summary.total_tasks * 100:.1f}%"
            if summary.total_tasks
            else "0%"
        )

        rows = "".join(_task_row(task, index) for index, task in enumerate(report.tasks))
        report_data = json.dumps(
            report.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        # Prevent untrusted report strings from terminating the JSON script element.
        report_data = (
            report_data.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
        )

        document = r"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="dark light">
  <title>EvalGuard Audit: __BENCHMARK__ - __AGENT__</title>
  <style>__CSS__</style>
</head>
<body>
  <main class="container">
    <header>
      <div class="header-row">
        <div>
          <h1>EvalGuard Audit Report</h1>
          <div class="meta">
            <strong>Benchmark:</strong> __BENCHMARK__ &bull;
            <strong>Agent:</strong> __AGENT__ &bull;
            <strong>Harness:</strong> __HARNESS__ &bull;
            <strong>Date:</strong> __CREATED__ &bull;
            <strong>Report ID:</strong> <code>__REPORT_ID__</code>
          </div>
        </div>
        <div class="controls">
          <button id="theme-toggle" type="button" aria-pressed="false">Switch to light mode</button>
          <button id="export-json" type="button">Export JSON</button>
          <button id="export-csv" type="button">Export CSV</button>
        </div>
      </div>
    </header>

    <section class="grid" aria-label="Audit summary">
      <article class="card"><div class="card-title">Total tasks</div><div class="card-val">__TOTAL_TASKS__</div></article>
      <article class="card"><div class="card-title">Raw pass rate</div><div class="card-val" style="color:var(--yellow)">__RAW_PCT__</div></article>
      <article class="card"><div class="card-title">Verified clean pass</div><div class="card-val" style="color:var(--green)">__CLEAN_PCT__</div></article>
      <article class="card"><div class="card-title">Boundary violations</div><div class="card-val" style="color:var(--red)">__BOUNDARY_VIOLATIONS__</div></article>
      <article class="card"><div class="card-title">Reward-hack flags</div><div class="card-val" style="color:var(--red)">__REWARD_HACK_FLAGS__</div></article>
    </section>

    <section aria-labelledby="task-heading">
      <h2 id="task-heading">Per-task audit findings</h2>
      <div class="toolbar">
        <div class="field">
          <label for="task-search">Search tasks and evidence</label>
          <input id="task-search" type="search" placeholder="Task ID, path, violation, or evidence…" autocomplete="off">
        </div>
        <div class="field">
          <label for="severity-filter">Boundary violation severity</label>
          <select id="severity-filter">
            <option value="all">All severities</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
            <option value="none">No boundary violations</option>
          </select>
        </div>
      </div>
      <p id="result-count" aria-live="polite"></p>
      <div class="table-scroll">
        <table id="task-table">
          <thead><tr>
            <th scope="col">Task ID</th><th scope="col">Agent result</th>
            <th scope="col">Boundary</th><th scope="col">Reward hack</th>
            <th scope="col">Contamination</th><th scope="col">Test integrity</th>
            <th scope="col">Duration</th>
          </tr></thead>
          <tbody>
            __ROWS__
            <tr id="no-results" hidden><td colspan="7">No tasks match the current filters.</td></tr>
          </tbody>
        </table>
      </div>
    </section>
    <footer>Generated by EvalGuard. This report is self-contained and runs locally in your browser; no external scripts or network requests are required.</footer>
  </main>
  <script type="application/json" id="report-data">__REPORT_DATA__</script>
  <script>__SCRIPT__</script>
</body>
</html>
"""
        replacements = {
            "__BENCHMARK__": _text(report.benchmark_id),
            "__AGENT__": _text(report.agent_id),
            "__HARNESS__": _text(report.harness_name),
            "__CREATED__": _text(report.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")),
            "__REPORT_ID__": _text(report.report_id),
            "__CSS__": _CSS,
            "__TOTAL_TASKS__": str(summary.total_tasks),
            "__RAW_PCT__": raw_pct,
            "__CLEAN_PCT__": clean_pct,
            "__BOUNDARY_VIOLATIONS__": str(summary.boundary_violations_total),
            "__REWARD_HACK_FLAGS__": str(summary.tasks_with_reward_hack),
            "__ROWS__": rows,
            "__REPORT_DATA__": report_data,
            "__SCRIPT__": _SCRIPT,
        }
        for marker, value in replacements.items():
            document = document.replace(marker, value)
        return document
