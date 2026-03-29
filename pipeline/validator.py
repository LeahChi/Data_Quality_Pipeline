"""
validator.py - Pluggable rule-based validation module.

Applies configurable validation rules to a profiled dataset. Rules are
type-aware and applied only to columns of the appropriate dtype.

Design rationale:
    Comparing the Newcastle Library Loans dataset (numeric, wide, time-series)
    with the Private Water Supplies dataset (categorical, narrow, registry-style)
    revealed that validation logic must be dataset-structure-aware:

    - Numeric datasets require plausibility checks (negatives, spikes, constants).
    - Categorical datasets require format/regex validation (postcodes, grid refs).
    - Neither set of checks is universally applicable.

    This module implements a pluggable rule architecture: each ValidationRule
    is a callable that accepts a column Series and returns a ValidationIssue
    (or None). Rules are registered per dtype category, making the pipeline
    extensible without modifying core logic.
"""

import re
import pandas as pd
from dataclasses import dataclass, field
from typing import Callable, Optional
from .profiler import ProfileResult, ColumnProfile


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ValidationIssue:
    """A single validation finding for a column."""
    column: str
    rule_name: str
    severity: str           # 'error' | 'warning' | 'info'
    message: str
    affected_count: int = 0


@dataclass
class ValidationResult:
    """Aggregated validation output for a full dataset."""
    dataset_name: str
    issues: list = field(default_factory=list)
    rules_applied: list = field(default_factory=list)

    @property
    def error_count(self):
        return sum(1 for i in self.issues if i.severity == "error")

    @property
    def warning_count(self):
        return sum(1 for i in self.issues if i.severity == "warning")


# ---------------------------------------------------------------------------
# Built-in validation rules
# ---------------------------------------------------------------------------

def rule_no_negatives(series: pd.Series, col_name: str) -> Optional[ValidationIssue]:
    """Flag columns with negative numeric values (plausibility check)."""
    count = int((series < 0).sum())
    if count > 0:
        return ValidationIssue(
            column=col_name,
            rule_name="no_negatives",
            severity="error",
            message=f"{count} negative value(s) found in numeric column.",
            affected_count=count,
        )
    return None


def rule_no_constant_columns(series: pd.Series, col_name: str) -> Optional[ValidationIssue]:
    """Flag columns that are constant (single unique value) across all rows."""
    if series.nunique(dropna=True) == 1:
        return ValidationIssue(
            column=col_name,
            rule_name="no_constant_columns",
            severity="warning",
            message="Column has only one unique value — may be uninformative or erroneous.",
            affected_count=int(series.notna().sum()),
        )
    return None


def rule_integers_only(series: pd.Series, col_name: str) -> Optional[ValidationIssue]:
    """Flag non-integer values in columns expected to hold integer counts."""
    non_int = series.notna() & (series % 1 != 0)
    count = int(non_int.sum())
    if count > 0:
        return ValidationIssue(
            column=col_name,
            rule_name="integers_only",
            severity="warning",
            message=f"{count} non-integer value(s) found in column expected to hold counts.",
            affected_count=count,
        )
    return None

def rule_category_consistency(series: pd.Series, col_name: str) -> Optional[ValidationIssue]:
    """
    Flag columns where the same value appears in multiple case/whitespace variants.

    For example: 'Yes', 'yes', 'YES', ' Yes' would all be flagged as
    inconsistent representations of the same value. 
    This is a representational data quality issue per Wang & Strong (1996).
    """
    if series.dtype != object:
        # Only applies to text columns
        return None

    normalised = series.dropna().astype(str).str.strip().str.lower()
    original = series.dropna().astype(str).str.strip()

    # Group original values by their normalised form in a dictionary
    """
    "yes": {"Yes", "yes", "YES"},
    "no":  {"No"} 
    """
    groups = {}
    for norm, orig in zip(normalised, original):
        if norm not in groups:
            groups[norm] = set()
        groups[norm].add(orig)

    # Flag any normalised value that maps to more than 1 original form
    inconsistent = {k: list(v) for k, v in groups.items() if len(v) > 1}

    if inconsistent:
        examples = list(inconsistent.values())[:3]
        count = sum(len(v) for v in inconsistent.values())
        return ValidationIssue(
            column=col_name,
            rule_name="category_consistency",
            severity="warning",
            message=(
                f"Category inconsistency detected — same value appears in multiple "
                f"forms. Examples: {examples}"
            ),
            affected_count=count,
        )
    return None


def make_regex_rule(
    pattern: str,
    rule_name: str,
    description: str,
    severity: str = "warning",
) -> Callable:
    """
    Factory for regex-based format validation rules.

    Args:
        pattern: Regular expression pattern that valid values must match.
        rule_name: Identifier string for the rule.
        description: Human-readable description of what is being validated.
        severity: 'error' or 'warning'.

    Returns:
        A validation rule function compatible with the validator pipeline.

    Example:
        postcode_rule = make_regex_rule(
            pattern=r'^[A-Z]{1,2}[0-9][0-9A-Z]? ?[0-9][A-Z]{2}$',
            rule_name='valid_postcode',
            description='UK postcode format',
        )
    """
    compiled = re.compile(pattern, re.IGNORECASE)

    def rule(series: pd.Series, col_name: str) -> Optional[ValidationIssue]:
        non_null = series.dropna().astype(str).str.strip()
        invalid = non_null[~non_null.str.match(compiled)]
        count = len(invalid)
        if count > 0:
            examples = invalid.head(3).tolist()
            return ValidationIssue(
                column=col_name,
                rule_name=rule_name,
                severity=severity,
                message=(
                    f"{count} value(s) do not match expected {description} format. "
                    f"Examples: {examples}"
                ),
                affected_count=count,
            )
        return None

    rule.__name__ = rule_name
    return rule


# Pre-built format rules derived from Private Water Supplies analysis
rule_valid_postcode = make_regex_rule(
    pattern=r"^[A-Z]{1,2}[0-9][0-9A-Z]?\s?[0-9][A-Z]{2}$",
    rule_name="valid_postcode",
    description="UK postcode",
)


rule_valid_os_grid_ref = make_regex_rule(
    pattern=r"^[A-Z]{2}\d{4,10}(\s[A-Z]{0,2}\d{0,10})?$",
    rule_name="valid_os_grid_ref",
    description="OS grid reference",
)


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------

# Default rule sets applied by column dtype
DEFAULT_NUMERIC_RULES = [rule_no_negatives, rule_no_constant_columns, rule_integers_only]
DEFAULT_TEXT_RULES = [rule_category_consistency]  # Format rules are dataset-specific — passed in per run


def validate(
    df: pd.DataFrame,
    profile_result: ProfileResult,
    numeric_rules: Optional[list] = None,
    text_rules: Optional[dict] = None,
    exclude_structural: bool = True,
) -> ValidationResult:
    """
    Apply validation rules to a dataset, guided by its profile.

    Args:
        df: The raw DataFrame to validate.
        profile_result: Output from profiler.profile().
        numeric_rules: List of rule functions to apply to numeric columns.
                       Defaults to DEFAULT_NUMERIC_RULES.
        text_rules: Dict mapping column names to lists of rule functions.
                    Used for format validation of specific text columns.
        exclude_structural: If True, skip columns classified as structural
                            (100% missing). Default True.

    Returns:
        ValidationResult with all issues found and rules applied.
    """
    numeric_rules = numeric_rules or DEFAULT_NUMERIC_RULES
    text_rules = text_rules or {}

    result = ValidationResult(dataset_name=profile_result.dataset_name)

    # Build a lookup of profiles by column name
    profile_map = {p.name: p for p in profile_result.column_profiles}

    for col in df.columns:
        col_profile: ColumnProfile = profile_map.get(col)
        if col_profile is None:
            continue

        # Skip structural (all-missing) columns
        if exclude_structural and col_profile.missingness_class == "structural":
            continue

        series = df[col]

        # Apply numeric rules
        if pd.api.types.is_numeric_dtype(series):
            for rule in numeric_rules:
                issue = rule(series, col)
                if issue:
                    result.issues.append(issue)
                if rule.__name__ not in result.rules_applied:
                    result.rules_applied.append(rule.__name__)

        # Apply default text rules to all text columns
        if series.dtype == object:
            for rule in DEFAULT_TEXT_RULES:
                issue = rule(series, col)
            if issue:
                result.issues.append(issue)
            if rule.__name__ not in result.rules_applied:
                result.rules_applied.append(rule.__name__)
        

        # Apply column-specific text rules
        if col in text_rules:
            for rule in text_rules[col]:
                issue = rule(series, col)
                if issue:
                    result.issues.append(issue)
                if rule.__name__ not in result.rules_applied:
                    result.rules_applied.append(rule.__name__)

    return result
