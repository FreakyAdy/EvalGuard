"""HTML report exporter producing standalone, modern visual audit pages."""

from __future__ import annotations

import html

from evalguard.report.schema import EvalGuardReport


class HtmlExporter:
    """Exports an EvalGuardReport to a self-contained, responsive HTML file."""

    @classmethod
    def export(cls, report: EvalGuardReport) -> str:
        s = report.summary
        clean_pct = (
            f"{(s.clean_passed_tasks / s.total_tasks * 100):.1f}%" if s.total_tasks else "0%"
        )
        raw_pct = f"{(s.agent_passed_tasks / s.total_tasks * 100):.1f}%" if s.total_tasks else "0%"

        task_rows = []
        for t in report.tasks:
            pass_badge = (
                '<span class="badge pass">PASS</span>'
                if t.agent_passed
                else '<span class="badge fail">FAIL</span>'
            )
            viol_badge = (
                f'<span class="badge warn">{len(t.violations)} viol</span>'
                if t.violations
                else '<span class="badge clean">hermetic</span>'
            )

            hack_score = t.reward_hack.confidence_score if t.reward_hack else 0.0
            hack_class = "fail" if hack_score >= 0.7 else ("warn" if hack_score >= 0.3 else "clean")
            hack_badge = f'<span class="badge {hack_class}">{hack_score:.2f}</span>'

            has_contam = any(cf.is_contaminated for cf in t.contamination_flags)
            contam_badge = (
                '<span class="badge warn">FLAGGED</span>'
                if has_contam
                else '<span class="badge clean">CLEAN</span>'
            )

            t_status = t.test_integrity.status.value if t.test_integrity else "PASS"
            test_class = (
                "fail" if t_status == "INVALID" else ("warn" if t_status == "SUSPECT" else "clean")
            )
            test_badge = f'<span class="badge {test_class}">{t_status}</span>'

            row = f"""
            <tr>
              <td><code>{html.escape(t.task_id)}</code></td>
              <td>{pass_badge}</td>
              <td>{viol_badge}</td>
              <td>{hack_badge}</td>
              <td>{contam_badge}</td>
              <td>{test_badge}</td>
            </tr>
            """
            task_rows.append(row)

        tbody = "\n".join(task_rows)

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>EvalGuard Audit: {html.escape(report.benchmark_id)} - {html.escape(report.agent_id)}</title>
  <style>
    :root {{
      --bg: #0d1117;
      --card: #161b22;
      --border: #30363d;
      --text: #c9d1d9;
      --text-muted: #8b949e;
      --accent: #58a6ff;
      --green: #3fb950;
      --red: #f85149;
      --yellow: #d29922;
    }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      margin: 0;
      padding: 2rem;
    }}
    .container {{ max-width: 1100px; margin: 0 auto; }}
    header {{ border-bottom: 1px solid var(--border); padding-bottom: 1.5rem; margin-bottom: 2rem; }}
    h1 {{ color: #ffffff; margin-bottom: 0.5rem; }}
    .meta {{ color: var(--text-muted); font-size: 0.9rem; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 2rem; }}
    .card {{ background: var(--card); border: 1px solid var(--border); border-radius: 6px; padding: 1.25rem; }}
    .card-title {{ font-size: 0.8rem; text-transform: uppercase; color: var(--text-muted); }}
    .card-val {{ font-size: 1.8rem; font-weight: bold; margin-top: 0.5rem; }}
    table {{ width: 100%; border-collapse: collapse; background: var(--card); border-radius: 6px; overflow: hidden; border: 1px solid var(--border); }}
    th, td {{ padding: 0.75rem 1rem; text-align: left; border-bottom: 1px solid var(--border); }}
    th {{ background: #21262d; font-size: 0.85rem; color: var(--text-muted); text-transform: uppercase; }}
    code {{ font-family: "JetBrains Mono", monospace; color: var(--accent); }}
    .badge {{ padding: 0.2rem 0.5rem; border-radius: 4px; font-size: 0.75rem; font-weight: bold; }}
    .badge.pass, .badge.clean {{ background: rgba(63, 185, 80, 0.15); color: var(--green); }}
    .badge.fail {{ background: rgba(248, 81, 73, 0.15); color: var(--red); }}
    .badge.warn {{ background: rgba(210, 153, 34, 0.15); color: var(--yellow); }}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <h1>🛡️ EvalGuard Audit Report</h1>
      <div class="meta">
        <strong>Benchmark:</strong> {html.escape(report.benchmark_id)} &bull;
        <strong>Agent:</strong> {html.escape(report.agent_id)} &bull;
        <strong>Harness:</strong> {html.escape(report.harness_name)} &bull;
        <strong>Date:</strong> {report.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")} &bull;
        <strong>ID:</strong> <code>{report.report_id}</code>
      </div>
    </header>

    <div class="grid">
      <div class="card">
        <div class="card-title">Total Tasks</div>
        <div class="card-val">{s.total_tasks}</div>
      </div>
      <div class="card">
        <div class="card-title">Raw Pass Rate</div>
        <div class="card-val" style="color: var(--yellow);">{raw_pct}</div>
      </div>
      <div class="card">
        <div class="card-title">Verified Clean Pass</div>
        <div class="card-val" style="color: var(--green);">{clean_pct}</div>
      </div>
      <div class="card">
        <div class="card-title">Boundary Violations</div>
        <div class="card-val" style="color: var(--red);">{s.boundary_violations_total}</div>
      </div>
      <div class="card">
        <div class="card-title">Reward Hack Flags</div>
        <div class="card-val" style="color: var(--red);">{s.tasks_with_reward_hack}</div>
      </div>
    </div>

    <h2>Per-Task Audit Findings</h2>
    <table>
      <thead>
        <tr>
          <th>Task ID</th>
          <th>Agent Result</th>
          <th>Boundary</th>
          <th>Reward Hack</th>
          <th>Contamination</th>
          <th>Test Case</th>
        </tr>
      </thead>
      <tbody>
        {tbody}
      </tbody>
    </table>
  </div>
</body>
</html>
"""
