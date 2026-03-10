"""
missing.py — Type-aware missingness detection.

We detect what is actually mossing, not just what pandas considers missing (NaN). 
This includes blank strings, text sentinels ("n/a", "unknown" etc.) and numeric sentinals.
"""

import pandas as pd
from dataclasses import dataclass, field
from .profiler import ProfileResult


NUMERIC_SENTINELS = [-999, -1, 999, 9999]
TEXT_SENTINELS = {"n/a", "na", "unknown", "-", "null", "none", "missing", ""}


@dataclass
class ColumnMissingness:
    column: str
    inferred_type: str
    nan_count: int
    blank_string_count: int
    text_sentinel_count: int
    numeric_sentinel_flags: list
    total_missing_estimate: int
    notes: list = field(default_factory=list)


@dataclass
class MissingnessResult:
    dataset_name: str
    column_results: list
    summary: dict


def detect_missingness(df, profiling_result, exclude_structural=True):
    #bUsing a dictionary for quick lookup of profiling info by column name.
    profile_map = {row["column"]: row for _, row in profiling_result.profile_df.iterrows()}

    column_results = []
    total_nan = total_blank = total_text_sentinel = total_numeric_sentinel_cols = 0

    for col in df.columns:
        p = profile_map.get(col)
        if p is None:
            # Crash prevention.
            continue
        if exclude_structural and p["missingness_class"] == "structural":
            # Skip structural (100% missing) columns, no need.
            continue

        series = df[col]
        nan_count = int(series.isna().sum())
        blank_count = text_sentinel_count = 0
        numeric_sentinel_flags = []
        notes = []

        if p["inferred_type"] == "text":
            # 1. Remove NaNs.
            # 2. Convert to string for consistent processing.
            # 3. Remove leading/trailing whitespace from every value.
            # 4. convert to lowercase for case-insensitive matching.
            stripped = series.dropna().astype(str).str.strip()
            blank_count = int((stripped == "").sum())
            lowered = stripped.str.lower()
            for sentinel in TEXT_SENTINELS:
                if sentinel == "":
                    continue
                count = int((lowered == str(sentinel)).sum())
                if count > 0:
                    text_sentinel_count += count
                    notes.append(f"Text sentinel '{sentinel}' found {count} time(s).")

        elif p["inferred_type"] == "numeric":
            for val in NUMERIC_SENTINELS:
                count = int((series == val).sum())
                if count > 0:
                    numeric_sentinel_flags.append({"value": val, "count": count})
                    notes.append(f"Numeric sentinel {val} found {count} time(s) — manual contextual validation recommended.")
            if numeric_sentinel_flags:
                total_numeric_sentinel_cols += 1

        # Total missing estimate combines all detectable hidden missingness.
        # Numeric sentinels are excluded because we cannot confirm if they are missing without domain knowledge.
        # They are flagged separately rather than counted as missing.
        total_missing_estimate = nan_count + blank_count + text_sentinel_count
        total_nan += nan_count
        total_blank += blank_count
        total_text_sentinel += text_sentinel_count

        column_results.append(ColumnMissingness(
            column=col, inferred_type=p["inferred_type"],
            nan_count=nan_count, blank_string_count=blank_count,
            text_sentinel_count=text_sentinel_count,
            numeric_sentinel_flags=numeric_sentinel_flags,
            total_missing_estimate=total_missing_estimate, notes=notes,
        ))

    summary = {
        "total_nan_values": total_nan,
        "total_blank_string_values": total_blank,
        "total_text_sentinel_values": total_text_sentinel,
        "numeric_sentinel_flagged_cols": total_numeric_sentinel_cols,
        "columns_with_any_missingness": sum(1 for r in column_results if r.total_missing_estimate > 0),
    }

    return MissingnessResult(dataset_name=profiling_result.dataset_name, column_results=column_results, summary=summary)