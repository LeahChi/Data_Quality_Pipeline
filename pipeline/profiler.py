"""
profiler.py - Structural and statistical dataset profiling module.

Performs column-level profiling: missingness classification, type inspection,
uniqueness, and basic descriptive statistics for numeric columns.

Design rationale:
    Analysis of the Newcastle Library Loans dataset (wide time-series, 205
    columns) revealed three distinct categories of missingness that require
    separate treatment:

        1. Structural missingness  - columns that are 100% empty, representing
                                     trailing time periods not yet recorded.
        2. Encoded missingness     - sentinel values masquerading as real data
                                     (e.g., -999, 'n/a', 'unknown').
        3. Residual missingness    - genuine partial missingness in otherwise
                                     populated columns.

    This three-tier classification is a key design principle extracted from
    the exploratory phase and directly informs the profiler's output schema.
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import Optional
from .loader import LoadResult

# Sentinel values to scan for, derived from exploratory analysis.
# The pipeline doesn't delete these, only flags them for contextual review.
NUMERIC_SENTINELS = [-999, -1, 999, 9999]
TEXT_SENTINELS = {"n/a", "unknown", "-", "null", "none", ""}


@dataclass
class ColumnProfile:
    """Profile summary for a single column."""
    name: str
    dtype: str
    num_values: int
    num_missing: int                      # fraction, so that it's comparable across columns and datasets
    missing_fraction: float
    missingness_class: str                # 'structural', 'partial', or 'complete'
    num_unique: int
    is_constant: bool
    example_value: str = None             # a non-missing example value for context
    sentinel_flags: list = field(default_factory=list)
    numeric_stats: Optional[dict] = None  # only populated for numeric columns


@dataclass
class ProfileResult:
    """Full profiling output for a dataset."""
    dataset_name: str
    num_rows: int
    num_cols: int
    structural_cols: list           # if 100% missing, could be trailing placeholders
    complete_cols: list             # 0% missing
    partial_cols: list              # some missing
    column_profiles: list           # list of ColumnProfile
    duplicate_count: int = 0
    fully_blank_rows: int = 0
    warnings: list = field(default_factory=list)

    @property
    def profile_df(self) -> pd.DataFrame:
        """
        Return column profiles as a flat DataFrame for downstream modules.

        Converts ColumnProfile dataclasses into rows, adding 'inferred_type'
        ('numeric' or 'text'), 'zero_count', and 'example_value' columns
        expected by missing.py and report.py.
        """
        records = []
        for cp in self.column_profiles:
            inferred_type = "numeric" if cp.dtype.startswith(("int", "float")) else "text"
            zero_count = cp.numeric_stats.get("zero_count") if cp.numeric_stats else None
            example_value = (
                str(cp.sentinel_flags[0].get("value", ""))
                if cp.sentinel_flags else cp.example_value
            )
            records.append({
                "column": cp.name,
                "dtype": cp.dtype,
                "inferred_type": inferred_type,
                "num_values": cp.num_values,
                "num_missing": cp.num_missing,
                "missing_fraction": cp.missing_fraction,
                "missingness_class": cp.missingness_class,
                "num_unique": cp.num_unique,
                "is_constant": cp.is_constant,
                "sentinel_flags": cp.sentinel_flags,
                "zero_count": zero_count,
                "example_value": example_value,
            })
        return pd.DataFrame(records)


def _classify_missingness(missing_fraction: float) -> str:
    """Classify a column's missingness into one of three tiers."""
    if missing_fraction == 1.0:
        return "structural"
    elif missing_fraction == 0.0:
        return "complete"
    else:
        return "partial"


def _check_numeric_sentinels(series: pd.Series) -> list:
    """Flag the set of numeric sentinel values present in a column."""
    found = []
    for val in NUMERIC_SENTINELS:
        if series.isin([val]).any():
            count = series.isin([val]).sum()
            found.append({"value": val, "count": int(count)})
    return found


def _check_text_sentinels(series: pd.Series) -> list:
    """Flag known text sentinel values present in an object column."""
    normalised = series.astype(str).str.strip().str.lower()
    found = []
    for sentinel in TEXT_SENTINELS:
        if normalised.isin([sentinel]).any():
            count = normalised.isin([sentinel]).sum()
            found.append({"value": sentinel, "count": int(count)})
    return found


def _numeric_stats(series: pd.Series) -> dict:
    """Calculates basic descriptive statistics for a numeric column."""
    desc = series.describe()
    # Non-integer check:
    # Count all non-null values, subtract them by the count of values that are integers.
    # Remainder is the count of decimals.
    # series % 1 gives the fractional part — 0.0 means it's a whole number
    non_integer_count = int(
        series.notna().sum() - (series.dropna() % 1 == 0).sum()
    )
    negative_count = int((series < 0).sum())
    return {
        "min": desc.get("min"),
        "max": desc.get("max"),
        "mean": round(desc.get("mean"), 4) if desc.get("mean") is not None else None,
        "std": round(desc.get("std"), 4) if desc.get("std") is not None else None,
        "negative_count": negative_count,
        "non_integer_count": non_integer_count,
    }


def profile(load_result: LoadResult) -> ProfileResult:
    """
    Generate a full structural and statistical profile of a loaded dataset.

    It iterates through every column in the dataset and computes structural metadata,
    missingness classification, uniqueness, and type-aware quality checks.

    Args:
        load_result: Output from loader.load_csv().

    Returns:
        ProfileResult containing per-column profiles and dataset-level summaries.
    """
    df = load_result.df
    warnings = []
    profiles = []

    structural_cols = []
    complete_cols = []
    partial_cols = []

    for col in df.columns:
        series = df[col]
        num_missing = int(series.isna().sum())          # Counting missing values as NaN
        num_values = int(series.notna().sum())
        missing_fraction = round(num_missing / len(series), 4) if len(series) > 0 else 0.0
        missingness_class = _classify_missingness(missing_fraction)
        num_unique = int(series.nunique(dropna=True))   # unique values excluding NaN
        is_constant = (num_unique == 1)

        # Sentinel detection is type-aware
        sentinel_flags = []
        numeric_stats = None

        if pd.api.types.is_numeric_dtype(series):
            # Numeric columns: check for sentinel values and compute descriptive statistics..
            sentinel_flags = _check_numeric_sentinels(series)
            numeric_stats = _numeric_stats(series)
        elif series.dtype == object:
            # Text columns: check for text sentinels ("n/a", "unknown" etc.)
            # Not computing numeric stats on text columns
            sentinel_flags = _check_text_sentinels(series)

        if sentinel_flags:
            warnings.append(
                f"Column '{col}': potential sentinel value(s) detected — "
                f"manual contextual validation recommended: {sentinel_flags}"
            )

        # Bucket columns by missingness class
        if missingness_class == "structural":
            structural_cols.append(col)
        elif missingness_class == "complete":
            complete_cols.append(col)
        else:
            partial_cols.append(col)

        # Get first non-null value as an example.
        first_valid = series.dropna().iloc[0] if series.notna().any() else "—"
        example_value = str(first_valid)[:50]  # cap at 50 chars to avoid overflow in report

        # One ColumnProfile per column — collected into profiles list.
        profiles.append(ColumnProfile(
            name=col,
            dtype=str(series.dtype),    # e.g. "int64", "float64", "object"
            num_values=num_values,
            num_missing=num_missing,
            missing_fraction=missing_fraction,
            missingness_class=missingness_class,
            num_unique=num_unique,
            is_constant=is_constant,
            example_value=example_value,
            sentinel_flags=sentinel_flags,
            numeric_stats=numeric_stats,
        ))

    # Dataset-level warnings added after the loop.
    if structural_cols:
        warnings.append(
            f"{len(structural_cols)} structural (100% missing) column(s) detected. "
            f"These are excluded from downstream validation steps."
        )

    # Duplicate row detection — excludes fully blank rows
    fully_blank_rows = int(df.isna().all(axis=1).sum())
    df_non_blank = df.dropna(how="all")
    duplicate_count = int(df_non_blank.duplicated().sum())

    if fully_blank_rows > 0:
        warnings.append(f"{fully_blank_rows} fully blank row(s) detected.")

    if duplicate_count > 0:
        examples = df_non_blank[df_non_blank.duplicated(keep=False)].head(3).to_dict(orient="records")
        warnings.append(f"{duplicate_count} duplicate row(s) detected (excluding blank rows). "
        f"Examples: {examples}")

    # Every following module (missing.py, validator.py, report.py) 
    # has everything it needs without re-computing anything.
    return ProfileResult(
        dataset_name=load_result.dataset_name,
        num_rows=load_result.num_rows,
        num_cols=load_result.num_cols,
        structural_cols=structural_cols,
        complete_cols=complete_cols,
        partial_cols=partial_cols,
        column_profiles=profiles,
        duplicate_count=duplicate_count,
        fully_blank_rows=fully_blank_rows,
        warnings=warnings,
    )
