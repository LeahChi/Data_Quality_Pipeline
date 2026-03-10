"""
report.py — Structured report generation (JSON + HTML).
"""

import json
from datetime import datetime
from pathlib import Path
from dataclasses import asdict

from .profiler import ProfileResult
from .missing import MissingnessResult
from .validator import ValidationResult


def generate_report(profiling_result, missingness_result, validation_result, output_dir="outputs", formats=None):
    formats = formats or ["json", "html"]
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    safe_name = profiling_result.dataset_name.replace(" ", "_").lower()
    outputs = {}

    if "json" in formats:
        path = output_path / f"{safe_name}_report.json"
        _write_json(profiling_result, missingness_result, validation_result, path)
        outputs["json"] = str(path)

    if "html" in formats:
        path = output_path / f"{safe_name}_report.html"
        _write_html(profiling_result, missingness_result, validation_result, path)
        outputs["html"] = str(path)

    return outputs


def _write_json(pr, mr, vr, path):
    report = {
        "generated_at": datetime.now().isoformat(),
        "dataset": pr.dataset_name,
        "structure": {
            "num_rows": pr.num_rows,
            "num_cols": pr.num_cols,
            "structural_cols_count": len(pr.structural_cols),
            "complete_cols_count": len(pr.complete_cols),
            "partial_cols_count": len(pr.partial_cols),
            "structural_cols": pr.structural_cols,
            "columns": pr.profile_df.to_dict(orient="records"),
        },
        "missingness": {
            "summary": mr.summary,
            "columns": [
                {
                    "column": r.column,
                    "inferred_type": r.inferred_type,
                    "nan_count": r.nan_count,
                    "blank_string_count": r.blank_string_count,
                    "text_sentinel_count": r.text_sentinel_count,
                    "numeric_sentinel_flags": r.numeric_sentinel_flags,
                    "total_missing_estimate": r.total_missing_estimate,
                    "notes": r.notes,
                }
                for r in mr.column_results
            ],
        },
        "validation": {
            "rules_applied": vr.rules_applied,
            "error_count": vr.error_count,
            "warning_count": vr.warning_count,
            "issues": [
                {
                    "column": i.column,
                    "rule": i.rule_name,
                    "severity": i.severity,
                    "message": i.message,
                    "affected_count": i.affected_count,
                }
                for i in vr.issues
            ],
        },
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)


def _badge(text, colour):
    return (
        f'<span style="background:{colour};color:#fff;padding:2px 8px;'
        f'border-radius:3px;font-size:0.78em;font-weight:600;">{text}</span>'
    )


def _severity_colour(s):
    return {"error": "#c0392b", "warning": "#e67e22", "info": "#2980b9"}.get(s, "#7f8c8d")


def _missingness_colour(c):
    return {"structural": "#c0392b", "partial": "#e67e22", "complete": "#27ae60"}.get(c, "#7f8c8d")


def _write_html(pr, mr, vr, path):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    miss_map = {r.column: r for r in mr.column_results}

    rows = ""
    for _, p in pr.profile_df.iterrows():
        mc = p["missingness_class"]
        mc_badge = _badge(mc, _missingness_colour(mc))
        type_badge = _badge(p["inferred_type"], "#2c3e50")
        mr_row = miss_map.get(p["column"])
        if mr_row and mr_row.numeric_sentinel_flags:
            sentinel_str = ", ".join(str(f["value"]) for f in mr_row.numeric_sentinel_flags)
        elif mr_row and mr_row.text_sentinel_count > 0:
            sentinel_str = f"{mr_row.text_sentinel_count} text sentinel(s)"
        else:
            sentinel_str = "—"

        rows += (
            f"<tr>"
            f"<td>{p['column']}</td>"
            f"<td>{type_badge}</td>"
            f"<td>{p['num_missing']} ({p['missing_fraction']:.1%})</td>"
            f"<td>{mc_badge}</td>"
            f"<td>{p['num_unique']}</td>"
            f"<td>{'Yes' if p['is_constant'] else 'No'}</td>"
            f"<td>{sentinel_str}</td>"
            f"<td style='max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;'>{p['example_value']}</td>"
            f"</tr>\n"
        )

    if not vr.issues:
        issues_html = "<p style='color:#27ae60;font-weight:600;'>No validation issues detected.</p>"
    else:
        issues_html = ""
        for issue in vr.issues:
            colour = _severity_colour(issue.severity)
            issues_html += (
                f"<div style='margin:8px 0;padding:12px 16px;"
                f"border-left:4px solid {colour};background:#f9f9f9;border-radius:0 4px 4px 0;'>"
                f"{_badge(issue.severity.upper(), colour)} "
                f"<strong>{issue.column}</strong> — "
                f"<code style='font-size:0.82em;color:#555;'>{issue.rule_name}</code><br>"
                f"<span style='color:#444;font-size:0.9em;'>{issue.message}</span>"
                f"</div>\n"
            )

    cards = (
        f'<div class="card" style="border-color:#c0392b;">'
        f'<div class="val" style="color:#c0392b;">{len(pr.structural_cols)}</div>'
        f'<div class="lbl">Structural columns<br>(100% missing)</div></div>'
        f'<div class="card" style="border-color:#e67e22;">'
        f'<div class="val" style="color:#e67e22;">{len(pr.partial_cols)}</div>'
        f'<div class="lbl">Partial missingness<br>columns</div></div>'
        f'<div class="card" style="border-color:#27ae60;">'
        f'<div class="val" style="color:#27ae60;">{len(pr.complete_cols)}</div>'
        f'<div class="lbl">Fully complete<br>columns</div></div>'
        f'<div class="card" style="border-color:#2c3e50;">'
        f'<div class="val">{vr.error_count}</div>'
        f'<div class="lbl">Validation<br>errors</div></div>'
        f'<div class="card" style="border-color:#e67e22;">'
        f'<div class="val" style="color:#e67e22;">{vr.warning_count}</div>'
        f'<div class="lbl">Validation<br>warnings</div></div>'
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>DQ Report: {pr.dataset_name}</title>
<style>
  body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
       max-width:1200px;margin:40px auto;padding:0 24px;color:#222;background:#fafafa;}}
  h1{{font-size:1.8rem;border-bottom:3px solid #2c3e50;padding-bottom:10px;color:#2c3e50;}}
  h2{{font-size:1.1rem;color:#2c3e50;margin-top:36px;text-transform:uppercase;
      letter-spacing:.05em;border-left:4px solid #2c3e50;padding-left:12px;}}
  .meta{{color:#666;font-size:0.85em;margin-bottom:24px;}}
  .cards{{display:flex;gap:16px;flex-wrap:wrap;margin:20px 0;}}
  .card{{flex:1;min-width:120px;padding:16px;border-radius:8px;border:2px solid #eee;
         background:#fff;text-align:center;}}
  .card .val{{font-size:2rem;font-weight:700;}}
  .card .lbl{{font-size:0.75rem;color:#666;margin-top:4px;line-height:1.4;}}
  table{{border-collapse:collapse;width:100%;font-size:0.85em;margin-top:12px;}}
  th{{background:#2c3e50;color:#fff;padding:10px 12px;text-align:left;font-weight:600;}}
  td{{padding:8px 12px;border-bottom:1px solid #eee;vertical-align:top;}}
  tr:hover td{{background:#f0f4f8;}}
  code{{background:#eee;padding:1px 5px;border-radius:3px;font-size:0.85em;}}
  .footer{{margin-top:48px;font-size:0.75em;color:#999;border-top:1px solid #eee;padding-top:16px;}}
</style>
</head>
<body>
<h1>Data Quality Report: {pr.dataset_name}</h1>
<p class="meta">
  Generated: {ts} &nbsp;|&nbsp;
  Rows: <strong>{pr.num_rows:,}</strong> &nbsp;|&nbsp;
  Columns: <strong>{pr.num_cols}</strong> &nbsp;|&nbsp;
  Rules applied: {', '.join(vr.rules_applied) or 'none'}
</p>
<h2>Dataset Overview</h2>
<div class="cards">{cards}</div>
<h2>Column Profiles</h2>
<table>
<thead>
<tr>
  <th>Column</th><th>Type</th><th>Missing</th><th>Class</th>
  <th>Unique</th><th>Constant?</th>
  <th>Sentinel Flags</th><th>Example Value</th>
</tr>
</thead>
<tbody>
{rows}
</tbody>
</table>
<h2>Validation Results</h2>
{issues_html}
<h2>Missingness Summary</h2>
<table>
<thead><tr><th>Metric</th><th>Value</th></tr></thead>
<tbody>
{"".join(f"<tr><td>{k.replace('_',' ').title()}</td><td>{v}</td></tr>" for k, v in mr.summary.items())}
</tbody>
</table>
{"<h2>Profiler Warnings</h2>" + "".join(f"<p>⚠ {w}</p>" for w in pr.warnings[:5]) + (f"<p>... and {len(pr.warnings)-5} more structural columns.</p>" if len(pr.warnings) > 5 else "") if pr.warnings else ""}
<div class="footer">Data Quality Profiling Pipeline — COMP3931 Individual Project</div>
</body>
</html>"""

    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
