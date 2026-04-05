"""
report.py — Structured report generation (JSON + HTML).

Generates two output formats per dataset:
    - JSON: machine-readable structured output for downstream processing
    - HTML: human-readable interactive report for direct inspection

A static template file (report_template.html) defines the structure, styling, and
interactive behaviour of the report. 
This module builds the dynamic content (column profiles, missingness chart, validation issues, data preview) 
and injects it into the template via placeholder replacement.

"""

import json
from datetime import datetime
from pathlib import Path
from dataclasses import asdict

from .profiler import ProfileResult
from .missing import MissingnessResult
from .validator import ValidationResult


def generate_report(profiling_result, missingness_result, validation_result, output_dir="outputs", formats=None, df=None):
    """
    Generate JSON and/or HTML reports for a profiled dataset.

    Args:
        profiling_result: Output from profiler.profile()
        missingness_result: Output from missing.detect_missingness()
        validation_result: Output from validator.validate()
        output_dir: Directory to write output files to. Created if not exists.
        formats: List of formats to generate. Defaults to ["json", "html"].
        df: Optional pandas DataFrame for raw data preview in HTML report.

    Returns:
        Dict mapping format names to output file paths.
    """
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
        _write_html(profiling_result, missingness_result, validation_result, path, df=df)
        outputs["html"] = str(path)

    return outputs


def _write_json(pr, mr, vr, path):
    """
    Write a structured JSON report for a profiled dataset.

    Args:
        pr: ProfileResult from profiler.profile()
        mr: MissingnessResult from missing.detect_missingness()
        vr: ValidationResult from validator.validate()
        path: Output file path.
    """
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


# ---------------------------------------------------------------------------
# HTML helper functions
# ---------------------------------------------------------------------------

def _badge(text, colour):
    """Return a coloured inline badge span element."""
    return (
        f'<span style="background:{colour};color:#fff;padding:2px 8px;'
        f'border-radius:3px;font-size:0.78em;font-weight:600;">{text}</span>'
    )


def _severity_colour(s):
    """Map a validation severity level to a display colour."""
    return {"error": "#c0392b", "warning": "#e67e22", "info": "#2980b9"}.get(s, "#7f8c8d")


def _missingness_colour(c):
    """Map a missingness class to a display colour."""
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

    # Extract labels (column names), values (% missing), and colours.
    # Colours match the missingness classification badges used elsewhere in the report.
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
    default_headers = "".join(f"<th>{col}</th>" for col in preview_cols)

    # Build table headers for all columns view
    all_headers = "".join(f"<th>{col}</th>" for col in df.columns)

    # Build table rows for default (20 col) view
    default_rows = ""
    for _, row in preview_rows.iterrows():
        cells = "".join(
            f"<td>{str(row[col]) if str(row[col]) != 'nan' else '—'}</td>"
            for col in preview_cols
        )
        default_rows += f"<tr>{cells}</tr>\n"

    # Build table rows for all columns, first 20 rows
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
    Preview Raw Data ({total_rows:,} rows x {total_cols} columns)
    </button>

    <!-- Modal Overlay -->
    <div id="dataModal" class="modal-overlay" onclick="closeOnOverlay(event)">
        <div class="modal-box">
            <button class="modal-close" onclick="closePreview()">X</button>
            <h2 style="margin-top:0;font-size:1.1rem;color:#2c3e50;">
                Raw Data Preview
            </h2>
            <p style="font-size:0.82em;color:#666;margin-bottom:8px;">
                Showing <span id="rowLabel">first 20</span> rows x
                <span id="colLabel">first 20</span> columns
                ({total_rows:,} total rows, {total_cols} total columns)
            </p>

            <!-- Expand buttons -->
            <div style="margin-bottom:12px;">
                <button class="expand-btn" onclick="expandCols()" id="colBtn">
                    Show all {total_cols} columns
                </button>
                <button class="expand-btn" onclick="expandRows()" id="rowBtn">
                    Show all {total_rows:,} rows
                </button>
            </div>

            <!-- Table container — horizontally and vertically scrollable -->
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
    // Store all four data state combinations for the preview modal.
    // These are pre-built at report generation time to avoid re-fetching data.
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


def _build_column_rows(pr, miss_map):
    """
    Build the HTML table rows for the Column Profiles section.

    Each row represents one column from the dataset, showing its type,
    missingness classification, unique value count, sentinel flags, and
    an example value.

    Args:
        pr: ProfileResult from profiler.profile()
        miss_map: Dict mapping column names to MissingnessColumnResult objects.

    Returns:
        HTML string of <tr> elements for the profile table body.
    """
    rows = ""
    for _, p in pr.profile_df.iterrows():
        mc = p["missingness_class"]
        mc_badge = _badge(mc, _missingness_colour(mc))
        type_badge = _badge(p["inferred_type"], "#2c3e50")
        mr_row = miss_map.get(p["column"])

        # Determine sentinel flag display string
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
            f"<td style='max-width:160px;overflow:hidden;text-overflow:ellipsis;"
            f"white-space:nowrap;'>{p['example_value']}</td>"
            f"</tr>\n"
        )
    return rows


def _build_issues_html(vr):
    """
    Build the HTML for the Validation Results section.

    Returns a success message if no issues were found, or a list of
    colour-coded issue blocks showing severity, column, rule name, and message.

    Args:
        vr: ValidationResult from validator.validate()

    Returns:
        HTML string for the validation issues section.
    """
    if not vr.issues:
        return "<p style='color:#27ae60;font-weight:600;'>No validation issues detected.</p>"

    issues_html = ""
    for issue in vr.issues:
        colour = _severity_colour(issue.severity)
        issues_html += (
            f"<div style='margin:8px 0;padding:12px 16px;"
            f"border-left:4px solid {colour};background:#f9f9f9;"
            f"border-radius:0 4px 4px 0;'>"
            f"{_badge(issue.severity.upper(), colour)} "
            f"<strong>{issue.column}</strong> — "
            f"<code style='font-size:0.82em;color:#555;'>{issue.rule_name}</code><br>"
            f"<span style='color:#444;font-size:0.9em;'>{issue.message}</span>"
            f"</div>\n"
        )
    return issues_html


def _build_cards(pr, vr):
    """
    Build the dataset overview summary cards.

    Shows structural, partial, and complete column counts alongside
    validation error/warning counts, duplicate rows, and blank rows.

    Args:
        pr: ProfileResult from profiler.profile()
        vr: ValidationResult from validator.validate()

    Returns:
        HTML string of card div elements.
    """
    return (
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


def _build_missingness_table(mr):
    """
    Build the HTML rows for the Missingness Summary table.

    Args:
        mr: MissingnessResult from missing.detect_missingness()

    Returns:
        HTML string of <tr> elements for the missingness summary table.
    """
    return "".join(
        f"<tr><td>{k.replace('_', ' ').title()}</td><td>{v}</td></tr>"
        for k, v in mr.summary.items()
    )


def _build_profiler_warnings(pr):
    """
    Build the Profiler Warnings section HTML.

    Shows up to 5 warnings with a count of any additional ones.
    Returns empty string if no warnings exist.

    Args:
        pr: ProfileResult from profiler.profile()

    Returns:
        HTML string for the profiler warnings section, or empty string.
    """
    if not pr.warnings:
        return ""

    warnings_html = (
        "<h2 class='section-toggle' onclick='toggleSection(this)'>"
        "Profiler Warnings</h2>"
        "<div class='section-content'>"
    )
    warnings_html += "".join(f"<p>⚠ {w}</p>" for w in pr.warnings[:5])
    if len(pr.warnings) > 5:
        warnings_html += f"<p>... and {len(pr.warnings) - 5} more warnings.</p>"
    warnings_html += "</div>"
    return warnings_html


def _write_html(pr, mr, vr, path, df=None):
    """
    Generate the interactive HTML report by injecting dynamic content
    into the report_template.html file.

    The template defines all static structure, CSS, and JavaScript.
    This function builds the dynamic content and replaces placeholders
    in the template with generated HTML strings.

    Args:
        pr: ProfileResult from profiler.profile()
        mr: MissingnessResult from missing.detect_missingness()
        vr: ValidationResult from validator.validate()
        path: Output file path for the generated report.
        df: Optional pandas DataFrame for raw data preview modal.
    """
    # Build a lookup of missingness results by column name
    miss_map = {r.column: r for r in mr.column_results}

    # Build all dynamic content blocks
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    cards = _build_cards(pr, vr)
    rows = _build_column_rows(pr, miss_map)
    issues_html = _build_issues_html(vr)
    missingness_table = _build_missingness_table(mr)
    chart = _build_bar_chart(pr)
    data_preview = _build_data_preview(df)
    profiler_warnings = _build_profiler_warnings(pr)
    rules_applied = ', '.join(vr.rules_applied) or 'none'

    # Load the HTML template from the same directory as this module
    template_path = Path(__file__).parent / "report_template.html"
    template = template_path.read_text(encoding="utf-8")

    # Replace all placeholders with generated content
    html = template
    html = html.replace("<!-- PLACEHOLDER:DATASET_NAME -->", pr.dataset_name)
    html = html.replace("<!-- PLACEHOLDER:TIMESTAMP -->", ts)
    html = html.replace("<!-- PLACEHOLDER:NUM_ROWS -->", f"{pr.num_rows:,}")
    html = html.replace("<!-- PLACEHOLDER:NUM_COLS -->", str(pr.num_cols))
    html = html.replace("<!-- PLACEHOLDER:RULES_APPLIED -->", rules_applied)
    html = html.replace("<!-- PLACEHOLDER:CARDS -->", cards)
    html = html.replace("<!-- PLACEHOLDER:DATA_PREVIEW -->", data_preview)
    html = html.replace("<!-- PLACEHOLDER:CHART -->", chart)
    html = html.replace("<!-- PLACEHOLDER:ROWS -->", rows)
    html = html.replace("<!-- PLACEHOLDER:ISSUES -->", issues_html)
    html = html.replace("<!-- PLACEHOLDER:MISSINGNESS_TABLE -->", missingness_table)
    html = html.replace("<!-- PLACEHOLDER:PROFILER_WARNINGS -->", profiler_warnings)

    with open(path, "w", encoding="utf-8") as f:
        f.write(html)