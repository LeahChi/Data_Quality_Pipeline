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


def generate_report(profiling_result, missingness_result, validation_result, output_dir="outputs", formats=None, df=None):
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
        _write_html(profiling_result, missingness_result, validation_result, path, df = df)
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

def _build_bar_chart(pr):
    """
    Build a Chart.js horizontal bar chart showing missingness % per column.
    Shows top 20 columns with partial missingness, sorted descending.
    Returns an HTML string containing a canvas element and inline JavaScript.

    Chart.js is loaded from a CDN — an internet connection is required
    to render the chart when opening the HTML report in a browser.

    Args:
        pr: ProfileResult from profiler.profile()

    Returns:
        HTML string containing the chart canvas and script tags.
    """
    df = pr.profile_df

    # Exclude structural columns (100% missing) — these are not meaningful
    # for a missingness distribution chart as they are placeholders, not
    # genuine data quality issues.
    chartable = df[df["missingness_class"] == "partial"].copy()
    chartable = chartable.sort_values("missing_fraction", ascending=False).head(20)

    # If no partial missingness exists, return a success message instead
    if chartable.empty:
        return "<p style='color:#27ae60;font-weight:600;'>No partial missingness detected.</p>"

    # Extract labels (column names), values (% missing), and colours
    # Colours match the missingness classification badges used elsewhere in the report
    labels = list(chartable["column"])
    values = [round(float(v) * 100, 1) for v in chartable["missing_fraction"]]
    colours = [
        "#e67e22" if c == "partial" else "#27ae60"
        for c in chartable["missingness_class"]
    ]

    # Serialise to JSON for injection into the JavaScript block
    labels_json = json.dumps(labels)
    values_json = json.dumps(values)
    colours_json = json.dumps(colours)

    return f"""
    <!-- Missingness bar chart — rendered using Chart.js 4.4.0 via CDN -->
    <!-- Requires internet connection to load the Chart.js library -->
    <canvas id="missingnessChart" style="max-height:500px;"></canvas>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js"></script>
    <script>
    (function() {{
        // Wrap in IIFE to avoid polluting global scope
        var ctx = document.getElementById('missingnessChart').getContext('2d');
        new Chart(ctx, {{
            type: 'bar',
            data: {{
                labels: {labels_json},
                datasets: [{{
                    label: 'Missing %',
                    data: {values_json},
                    backgroundColor: {colours_json},
                    borderRadius: 4,
                }}]
            }},
            options: {{
            // indexAxis: 'y' makes this a horizontal bar chart
            // which is easier to read for long column names
                indexAxis: 'y',
                responsive: true,
                plugins: {{
                // Hide the legend since colours are self-explanatory
                    legend: {{ display: false }},
                    tooltip: {{
                        callbacks: {{
                        // Format tooltip to show percentage
                            label: function(context) {{
                                return context.parsed.x.toFixed(1) + '% missing';
                            }}
                        }}
                    }}
                }},
                scales: {{
                    x: {{
                        min: 0,
                        max: 100,
                        title: {{ display: true, text: 'Missing (%)' }},
                        ticks: {{ callback: function(v) {{ return v + '%'; }} }}
                    }},
                    y: {{
                        ticks: {{ font: {{ size: 11 }} }}
                    }}
                }}
            }}
        }});
    }})();
    </script>
    <p style="font-size:0.78em;color:#999;margin-top:8px;">
        Top 20 columns by missing fraction. Structural (100% missing) columns excluded.
    </p>"""

def _build_data_preview(df):
    """
    Build a modal popup showing the raw dataset rows.

    Displays first 20 rows and first 20 columns by default, with buttons
    to expand to all rows and all columns. Returns empty string if df is None.

    Args:
        df: pandas DataFrame from loader.load_csv()

    Returns:
        HTML string containing the modal overlay and trigger button.
    """
    if df is None:
        # If no dataframe was passed, hide the preview entirely
        return ""

    total_rows = len(df)
    total_cols = len(df.columns)

    # Default view — first 20 rows, first 20 columns
    preview_rows = df.head(20)
    preview_cols = list(df.columns[:20])

    # Build table headers for default (20 col) view
    default_headers = "".join(
        f"<th>{col}</th>" for col in preview_cols
    )

    # Build table headers for all columns view
    all_headers = "".join(
        f"<th>{col}</th>" for col in df.columns
    )

    # Build table rows for default (20 col) view
    default_rows = ""
    for _, row in preview_rows.iterrows():
        cells = "".join(
            f"<td>{str(row[col]) if str(row[col]) != 'nan' else '—'}</td>"
            for col in preview_cols
        )
        default_rows += f"<tr>{cells}</tr>\n"

    # Build table rows for all columns view
    all_rows = ""
    for _, row in preview_rows.iterrows():
        cells = "".join(
            f"<td>{str(row[col]) if str(row[col]) != 'nan' else '—'}</td>"
            for col in df.columns
        )
        all_rows += f"<tr>{cells}</tr>\n"

    # Build all rows for default columns view
    all_data_rows = ""
    for _, row in df.iterrows():
        cells = "".join(
            f"<td>{str(row[col]) if str(row[col]) != 'nan' else '—'}</td>"
            for col in preview_cols
        )
        all_data_rows += f"<tr>{cells}</tr>\n"

    # Build all rows, all columns view
    all_data_all_cols = ""
    for _, row in df.iterrows():
        cells = "".join(
            f"<td>{str(row[col]) if str(row[col]) != 'nan' else '—'}</td>"
            for col in df.columns
        )
        all_data_all_cols += f"<tr>{cells}</tr>\n"

    return f"""
    <!-- Data Preview Button -->
    <button class="preview-btn" onclick="openPreview()">
    Preview Raw Data ({total_rows:,} rows × {total_cols} columns)
    </button>

    <!-- Modal Overlay -->
    <div id="dataModal" class="modal-overlay" onclick="closeOnOverlay(event)">
        <div class="modal-box">
            <button class="modal-close" onclick="closePreview()">✕</button>
            <h2 style="margin-top:0;font-size:1.1rem;color:#2c3e50;">
                Raw Data Preview
            </h2>
            <p style="font-size:0.82em;color:#666;margin-bottom:8px;">
                Showing <span id="rowLabel">first 20</span> rows ×
                <span id="colLabel">first 20</span> columns
                ({total_rows:,} total rows, {total_cols} total columns)
            </p>

        <!-- Expand buttons -->
        <div style="margin-bottom:12px;">
            <button class="expand-btn" onclick="expandCols()" id="colBtn">
                Show all {total_cols} columns →
            </button>
            <button class="expand-btn" onclick="expandRows()" id="rowBtn">
                Show all {total_rows:,} rows →
            </button>
        </div>

        <!-- Table container -->
        <div style="overflow-x:auto;max-height:60vh;overflow-y:auto;">
            <table class="modal-table" id="previewTable">
                <thead id="previewHead">
                    <tr>{default_headers}</tr>
                </thead>
                <tbody id="previewBody">
                    {default_rows}
                </tbody>
            </table>
        </div>
    </div>
</div>

    <script>
    // Store all data states for the preview modal
    var _allHeaders = `<tr>{all_headers}</tr>`;
    var _defaultHeaders = `<tr>{default_headers}</tr>`;
    var _defaultRows = `{default_rows.replace('`', '"')}`;
    var _allRows = `{all_rows.replace('`', '"')}`;
    var _allDataRows = `{all_data_rows.replace('`', '"')}`;
    var _allDataAllCols = `{all_data_all_cols.replace('`', '"')}`;

    var showingAllCols = false;
    var showingAllRows = false;

function openPreview() {{
    // Reset to default view each time modal opens
    showingAllCols = false;
    showingAllRows = false;
    document.getElementById('previewHead').innerHTML = _defaultHeaders;
    document.getElementById('previewBody').innerHTML = _defaultRows;
    document.getElementById('colLabel').textContent = 'first 20';
    document.getElementById('rowLabel').textContent = 'first 20';
    document.getElementById('colBtn').style.display = 'inline-block';
    document.getElementById('rowBtn').style.display = 'inline-block';
    document.getElementById('dataModal').style.display = 'block';
    document.body.style.overflow = 'hidden';
}}

function closePreview() {{
    document.getElementById('dataModal').style.display = 'none';
    document.body.style.overflow = '';
}}

function closeOnOverlay(event) {{
    // Close if user clicks the dark overlay, not the modal box itself
    if (event.target === document.getElementById('dataModal')) {{
        closePreview();
    }}
}}

function expandCols() {{
    // Switch to all columns view
    showingAllCols = true;
    document.getElementById('previewHead').innerHTML = _allHeaders;
    document.getElementById('previewBody').innerHTML = 
        showingAllRows ? _allDataAllCols : _allRows;
    document.getElementById('colLabel').textContent = 'all';
    document.getElementById('colBtn').style.display = 'none';
}}

function expandRows() {{
    // Switch to all rows view
    showingAllRows = true;
    document.getElementById('previewBody').innerHTML = 
        showingAllCols ? _allDataAllCols : _allDataRows;
    document.getElementById('rowLabel').textContent = 'all';
    document.getElementById('rowBtn').style.display = 'none';
}}
</script>
"""

def _write_html(pr, mr, vr, path, df=None):
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
         f'<div class="card" style="border-color:#8e44ad;">'
        f'<div class="val" style="color:#8e44ad;">{pr.duplicate_count}</div>'
        f'<div class="lbl">Duplicate<br>rows</div></div>'
        f'<div class="card" style="border-color:#7f8c8d;">'
        f'<div class="val" style="color:#7f8c8d;">{pr.fully_blank_rows}</div>'
        f'<div class="lbl">Fully blank<br>rows</div></div>'
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
  .section-toggle{{cursor:pointer;user-select:none;display:flex;
                   align-items:center;justify-content:space-between;}}
  .section-toggle::after{{content:'hide ▲';font-size:0.7em;color:#999;margin-left:8px;}}
  .section-toggle.collapsed::after{{content:'show ▼';}}
  .section-content{{transition:opacity 0.2s ease;}}
  .section-content.hidden{{display:none;}}
   .modal-overlay{{display:none;position:fixed;top:0;left:0;width:100%;height:100%;
                  background:rgba(0,0,0,0.5);z-index:1000;overflow:auto;}}
  .modal-box{{background:#fff;margin:40px auto;padding:24px;max-width:95%;
              border-radius:8px;position:relative;}}
  .modal-close{{position:absolute;top:12px;right:16px;font-size:1.4rem;
                cursor:pointer;color:#666;border:none;background:none;}}
  .modal-close:hover{{color:#c0392b;}}
  .modal-table{{border-collapse:collapse;width:100%;font-size:0.82em;overflow-x:auto;display:block;}}
  .modal-table th{{background:#2c3e50;color:#fff;padding:8px 10px;
                   text-align:left;white-space:nowrap;}}
  .modal-table td{{padding:6px 10px;border-bottom:1px solid #eee;white-space:nowrap;}}
  .modal-table tr:hover td{{background:#f0f4f8;}}
  .preview-btn{{margin-top:12px;padding:8px 16px;background:#2c3e50;color:#fff;
                border:none;border-radius:4px;font-size:0.85em;cursor:pointer;}}
  .preview-btn:hover{{background:#34495e;}}
  .expand-btn{{margin:8px 4px 0 0;padding:6px 12px;background:#f0f4f8;
               border:1px solid #ddd;border-radius:4px;font-size:0.82em;cursor:pointer;}}
  .expand-btn:hover{{background:#e0e8f0;}}
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
<h2 class="section-toggle" onclick="toggleSection(this)">Dataset Overview</h2>
<div class="section-content">
<div class="cards">{cards}</div>
{_build_data_preview(df)}
</div>
<h2 class="section-toggle" onclick="toggleSection(this)">Missingness Distribution</h2>
<div class="section-content">
{_build_bar_chart(pr)}
</div>

<h2 class="section-toggle" onclick="toggleSection(this)">Column Profiles</h2>
<div class="section-content">
<div style="display:flex;gap:12px;margin:12px 0;align-items:center;flex-wrap:wrap;">
    <!-- Filter by missingness class -->
    <div>
        <label for="classFilter" style="font-size:0.85em;color:#666;margin-right:6px;">
            Filter by class:
        </label>
        <select id="classFilter" onchange="filterTable()"
                style="padding:6px 10px;border:1px solid #ddd;border-radius:4px;
                       font-size:0.85em;background:#fff;">
            <option value="all">All columns</option>
            <option value="structural">Structural</option>
            <option value="partial">Partial</option>
            <option value="complete">Complete</option>
        </select>
    </div>
    <!-- Search by column name (case insensitive) -->
    <div>
        <label for="colSearch" style="font-size:0.85em;color:#666;margin-right:6px;">
            Search column:
        </label>
        <input id="colSearch" type="text" oninput="filterTable()"
               placeholder="e.g. Library, Date..."
               style="padding:6px 10px;border:1px solid #ddd;border-radius:4px;
                      font-size:0.85em;width:200px;"/>
    </div>
    <!-- Row count indicator -->
    <div id="rowCount" style="font-size:0.82em;color:#999;margin-left:auto;"></div>
    <button id="showAllBtn" onclick="showAll()"
            style="display:none;padding:6px 14px;background:#2c3e50;color:#fff;
                   border:none;border-radius:4px;font-size:0.82em;cursor:pointer;">
        Show all columns
    </button>
</div>
<table id="profileTable">
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
</div>

<h2 class="section-toggle" onclick="toggleSection(this)">Validation Results</h2>
<div class="section-content">
{issues_html}
</div>

<h2 class="section-toggle" onclick="toggleSection(this)">Missingness Summary</h2>
<div class="section-content">
<table>
<thead><tr><th>Metric</th><th>Value</th></tr></thead>
<tbody>
{"".join(f"<tr><td>{k.replace('_',' ').title()}</td><td>{v}</td></tr>" for k, v in mr.summary.items())}
</tbody>
</table>
</div>

{"<h2 class='section-toggle' onclick='toggleSection(this)'>Profiler Warnings</h2><div class='section-content'>" + "".join(f"<p>⚠ {w}</p>" for w in pr.warnings[:5]) + (f"<p>... and {len(pr.warnings)-5} more structural columns.</p>" if len(pr.warnings) > 5 else "") + "</div>" if pr.warnings else ""}
<div class="footer">Data Quality Profiling Pipeline — COMP3931 Individual Project</div>
<script>
// Default number of rows to display before user clicks "Show all"
// Filter the column profiles table by missingness class and/or column name.
// Filters are applied simultaneously on every change.
var showAllRows = false;
var PAGE_SIZE = 10;

function filterTable(event) {{
    // When filters change, reset back to paginated view
    if (event && event.type !== 'click') {{
        showAllRows = false;
    }}

    var classFilter = document.getElementById('classFilter').value.toLowerCase();
    var searchTerm = document.getElementById('colSearch').value.toLowerCase().trim();

    var rows = document.querySelectorAll('#profileTable tbody tr');
    var matchedRows = [];

    // First pass — find all rows matching current filters
    rows.forEach(function(row) {{
        var colName = row.cells[0].textContent.toLowerCase();
        var missClass = row.cells[3].textContent.toLowerCase().trim();
        var matchesClass = (classFilter === 'all') || missClass.includes(classFilter);
        var matchesSearch = (searchTerm === '') || colName.includes(searchTerm);

        if (matchesClass && matchesSearch) {{
            matchedRows.push(row);
        }} else {{
            // Hide rows that don't match filters at all
            row.style.display = 'none';
        }}
    }});

    // Second pass — apply pagination to matched rows
    var visibleCount = 0;
    matchedRows.forEach(function(row, index) {{
        if (showAllRows || index < PAGE_SIZE) {{
            row.style.display = '';
            visibleCount++;
        }} else {{
            row.style.display = 'none';
        }}
    }});

    // Update row count indicator
    document.getElementById('rowCount').textContent =
        'Showing ' + visibleCount + ' of ' + matchedRows.length + ' matching columns';

    // Show or hide the "Show all" button
    var btn = document.getElementById('showAllBtn');
    if (matchedRows.length > PAGE_SIZE && !showAllRows) {{
        btn.style.display = 'inline-block';
        btn.textContent = 'Show all ' + matchedRows.length + ' columns ↓';
    }} else {{
        btn.style.display = 'none';
    }}
}}

function showAll() {{
    // Reveal all matching rows
    showAllRows = true;
    filterTable();
}}

function toggleSection(header) {{
    // Toggle collapsed state on the header
    header.classList.toggle('collapsed');
    // Find the next sibling section-content div and hide/show it
    var content = header.nextElementSibling;
    if (content && content.classList.contains('section-content')) {{
        content.classList.toggle('hidden');
    }}
}}

// Run on page load to initialise pagination
window.onload = function() {{ filterTable(); }};
</script>
</body>
</html>"""

    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
