"""
tests/test_pipeline.py - Unit tests for the data quality profiling pipeline.

Tests cover the core logic of each module independently, using synthetic
DataFrames to avoid dependency on external data files.

All test classes inherit from unittest.TestCase for proper test discovery.
Tests are organised by module: profiler, validator, loader, and integration.
"""

import sys
import os
import unittest
import pandas as pd
import numpy as np
from pathlib import Path

# Ensure pipeline package is importable from the project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pipeline.profiler import (
    profile,
    _classify_missingness,
    _check_numeric_sentinels,
    _check_text_sentinels,
)
from pipeline.validator import (
    validate,
    rule_no_negatives,
    rule_no_constant_columns,
    rule_integers_only,
    rule_category_consistency,
    make_regex_rule,
)
from pipeline.loader import load_csv, LoadResult


# ---------------------------------------------------------------------------
# Helper — construct a LoadResult from a synthetic DataFrame
# ---------------------------------------------------------------------------

def make_load_result(df: pd.DataFrame, name: str = "test_dataset") -> LoadResult:
    """
    Construct a LoadResult from a synthetic DataFrame for testing purposes.
    Mirrors the output of load_csv() without requiring a real CSV file.
    """
    return LoadResult(
        df=df,
        dataset_name=name,
        source_path="/fake/path.csv",
        num_rows=df.shape[0],
        num_cols=df.shape[1],
        column_names=df.columns.tolist(),
        dtypes={col: str(df[col].dtype) for col in df.columns},
        encoding_used="utf-8",
    )


# ---------------------------------------------------------------------------
# Profiler — missingness classification
# ---------------------------------------------------------------------------

class TestClassifyMissingness(unittest.TestCase):
    """Tests for the three-tier missingness classification logic."""
    # - structural (1.0): placeholder columns, e.g. future time periods
    # - partial (0-1): genuine quality concern
    # - complete (0.0): no missing values

    def test_structural(self):
        """100% missing fraction should be classified as structural."""
        self.assertEqual(_classify_missingness(1.0), "structural")

    def test_complete(self):
        """0% missing fraction should be classified as complete."""
        self.assertEqual(_classify_missingness(0.0), "complete")

    def test_partial(self):
        """Any fraction between 0 and 1 should be classified as partial."""
        self.assertEqual(_classify_missingness(0.5), "partial")

    def test_partial_low(self):
        """Very low missing fraction should still be partial, not complete."""
        self.assertEqual(_classify_missingness(0.01), "partial")

    def test_partial_high(self):
        """Very high missing fraction should still be partial, not structural."""
        self.assertEqual(_classify_missingness(0.99), "partial")


# ---------------------------------------------------------------------------
# Profiler — numeric sentinel detection
# ---------------------------------------------------------------------------

class TestNumericSentinels(unittest.TestCase):
    """Tests for predefined numeric sentinel value detection. 
    The sentinel values monitored: -999, -1, 999, 9999"""

    def test_detects_999(self):
        """999 is a known sentinel and should be flagged."""
        s = pd.Series([1, 2, 999, 4])
        flags = _check_numeric_sentinels(s)
        self.assertTrue(any(f["value"] == 999 for f in flags))

    def test_detects_negative_999(self):
        """-999 is a known sentinel and should be flagged."""
        s = pd.Series([1, 2, -999, 4])
        flags = _check_numeric_sentinels(s)
        self.assertTrue(any(f["value"] == -999 for f in flags))

    def test_detects_negative_1(self):
        """-1 is a known sentinel and should be flagged."""
        s = pd.Series([5, -1, 3])
        flags = _check_numeric_sentinels(s)
        self.assertTrue(any(f["value"] == -1 for f in flags))

    def test_no_false_positive(self):
        """Clean numeric data should produce no sentinel flags."""
        s = pd.Series([10, 20, 30, 40])
        flags = _check_numeric_sentinels(s)
        self.assertEqual(flags, [])

    def test_count_is_correct(self):
        """Sentinel flag count should reflect actual occurrences."""
        s = pd.Series([999, 999, 1, 2])
        flags = _check_numeric_sentinels(s)
        flag = next(f for f in flags if f["value"] == 999)
        self.assertEqual(flag["count"], 2)


# ---------------------------------------------------------------------------
# Profiler — text sentinel detection
# ---------------------------------------------------------------------------

class TestTextSentinels(unittest.TestCase):
    """Tests for common text sentinel encoding detection."""

    def test_detects_na_string(self):
        """'n/a' should be detected as a text sentinel."""
        s = pd.Series(["Leeds", "n/a", "Bradford"])
        flags = _check_text_sentinels(s)
        self.assertTrue(any(f["value"] == "n/a" for f in flags))

    def test_case_insensitive(self):
        """Sentinel detection should be case-insensitive."""
        s = pd.Series(["Unknown", "Sheffield"])
        flags = _check_text_sentinels(s)
        self.assertTrue(any(f["value"] == "unknown" for f in flags))

    def test_detects_null_string(self):
        """'null' should be detected as a text sentinel."""
        s = pd.Series(["null", "Leeds"])
        flags = _check_text_sentinels(s)
        self.assertTrue(any(f["value"] == "null" for f in flags))

    def test_no_false_positive(self):
        """Clean text data should produce no sentinel flags."""
        s = pd.Series(["Leeds", "Bradford", "York"])
        flags = _check_text_sentinels(s)
        self.assertEqual(flags, [])


# ---------------------------------------------------------------------------
# Profiler — column classification
# ---------------------------------------------------------------------------

class TestProfile(unittest.TestCase):
    """Tests for the full profile() function output."""

    def test_structural_col_detected(self):
        """A 100% NaN column should appear in structural_cols."""
        df = pd.DataFrame({
            "id": [1, 2, 3],
            "empty": [np.nan, np.nan, np.nan],
        })
        result = profile(make_load_result(df))
        self.assertIn("empty", result.structural_cols)

    def test_complete_col_classified(self):
        """A fully populated column should appear in complete_cols."""
        df = pd.DataFrame({"name": ["Alice", "Bob", "Carol"]})
        result = profile(make_load_result(df))
        self.assertIn("name", result.complete_cols)

    def test_partial_col_classified(self):
        """A column with some NaN should appear in partial_cols."""
        df = pd.DataFrame({"score": [1.0, np.nan, 3.0]})
        result = profile(make_load_result(df))
        self.assertIn("score", result.partial_cols)

    def test_constant_col_flagged(self):
        """A column with one unique value should be flagged as constant."""
        df = pd.DataFrame({"status": ["active", "active", "active"]})
        result = profile(make_load_result(df))
        col_profile = next(p for p in result.column_profiles if p.name == "status")
        self.assertTrue(col_profile.is_constant)

    def test_num_rows_and_cols(self):
        """ProfileResult should correctly report dataset dimensions."""
        df = pd.DataFrame({"a": [1, 2], "b": [3, 4], "c": [5, 6]})
        result = profile(make_load_result(df))
        self.assertEqual(result.num_rows, 2)
        self.assertEqual(result.num_cols, 3)

    def test_example_value_populated(self):
        """Each ColumnProfile should have a non-empty example value."""
        df = pd.DataFrame({"city": ["Leeds", "Bradford"]})
        result = profile(make_load_result(df))
        col = next(p for p in result.column_profiles if p.name == "city")
        self.assertIsNotNone(col.example_value)
        self.assertNotEqual(col.example_value, "")


# ---------------------------------------------------------------------------
# Validator — built-in rules
# ---------------------------------------------------------------------------

class TestRuleNoNegatives(unittest.TestCase):
    """Tests for the no_negatives validation rule."""

    def test_flags_negatives(self):
        """Negative values should produce a validation issue."""
        s = pd.Series([1, -5, 3])
        issue = rule_no_negatives(s, "count")
        self.assertIsNotNone(issue)
        self.assertEqual(issue.affected_count, 1)

    def test_passes_clean(self):
        """All non-negative values should produce no issue."""
        s = pd.Series([1, 2, 3])
        self.assertIsNone(rule_no_negatives(s, "count"))

    def test_passes_zeros(self):
        """Zero values should not be flagged as negative."""
        s = pd.Series([0, 0, 5])
        self.assertIsNone(rule_no_negatives(s, "count"))


class TestRuleNoConstantColumns(unittest.TestCase):
    """Tests for the no_constant_columns validation rule."""

    def test_flags_constant(self):
        """A column with one unique value should be flagged."""
        s = pd.Series([7, 7, 7])
        issue = rule_no_constant_columns(s, "col")
        self.assertIsNotNone(issue)

    def test_passes_varied(self):
        """A column with multiple unique values should not be flagged."""
        s = pd.Series([1, 2, 3])
        self.assertIsNone(rule_no_constant_columns(s, "col"))


class TestRuleIntegersOnly(unittest.TestCase):
    """Tests for the integers_only validation rule."""

    def test_flags_floats(self):
        """Non-integer float values should be flagged."""
        s = pd.Series([1.0, 2.5, 3.0])
        issue = rule_integers_only(s, "count")
        self.assertIsNotNone(issue)
        self.assertEqual(issue.affected_count, 1)

    def test_passes_whole_numbers(self):
        """Float values that are whole numbers should not be flagged."""
        s = pd.Series([1.0, 2.0, 3.0])
        self.assertIsNone(rule_integers_only(s, "count"))


class TestRuleCategoryConsistency(unittest.TestCase):
    """Tests for the category_consistency validation rule."""

    def test_flags_case_inconsistency(self):
        """Mixed case variants of the same value should be flagged."""
        s = pd.Series(["Monday", "monday", "Tuesday"])
        issue = rule_category_consistency(s, "day")
        self.assertIsNotNone(issue)

    def test_passes_consistent(self):
        """Consistent casing should produce no issue."""
        s = pd.Series(["Monday", "Tuesday", "Wednesday"])
        self.assertIsNone(rule_category_consistency(s, "day"))

    def test_flags_whitespace_inconsistency(self):
        """Values with internal whitespace differences should be flagged."""
        s = pd.Series(["NO MKT", "No Mkt", "Bradford"])
        issue = rule_category_consistency(s, "notes")
        self.assertIsNotNone(issue)


class TestRegexRule(unittest.TestCase):
    """Tests for the make_regex_rule factory function."""

    def setUp(self):
        self.postcode_rule = make_regex_rule(
            r"^[A-Z]{1,2}[0-9][0-9A-Z]?\s?[0-9][A-Z]{2}$",
            "postcode",
            "UK postcode"
        )

    def test_valid_postcode_passes(self):
        """Valid UK postcodes should produce no issue."""
        s = pd.Series(["LS1 4AP", "BD1 1AA"])
        self.assertIsNone(self.postcode_rule(s, "postcode"))

    def test_invalid_postcode_flagged(self):
        """Invalid postcode format should produce an issue."""
        s = pd.Series(["LS1 4AP", "INVALID"])
        issue = self.postcode_rule(s, "postcode")
        self.assertIsNotNone(issue)
        self.assertEqual(issue.affected_count, 1)


# ---------------------------------------------------------------------------
# Validator — integration tests
# ---------------------------------------------------------------------------

class TestValidate(unittest.TestCase):
    """Integration tests for the full validate() function."""

    def test_returns_issues_for_negatives(self):
        """Negative values in a numeric column should produce a validation issue."""
        df = pd.DataFrame({"loans": [10, -1, 5]})
        lr = make_load_result(df)
        pr = profile(lr)
        vr = validate(df, pr)
        self.assertTrue(any(i.rule_name == "no_negatives" for i in vr.issues))

    def test_structural_cols_excluded(self):
        """Structural (100% missing) columns should be excluded from validation."""
        df = pd.DataFrame({
            "loans": [1, 2, 3],
            "empty": [np.nan, np.nan, np.nan],
        })
        lr = make_load_result(df)
        pr = profile(lr)
        vr = validate(df, pr, exclude_structural=True)
        self.assertFalse(any(i.column == "empty" for i in vr.issues))

    def test_clean_dataset_no_issues(self):
        """A fully clean dataset should produce no validation issues."""
        df = pd.DataFrame({
            "name": ["Alice", "Bob", "Carol"],
            "score": [10, 20, 30],
        })
        lr = make_load_result(df)
        pr = profile(lr)
        vr = validate(df, pr)
        self.assertEqual(vr.error_count, 0)


# ---------------------------------------------------------------------------
# Loader — encoding fallback
# ---------------------------------------------------------------------------

class TestLoader(unittest.TestCase):
    """Tests for the load_csv() function."""

    def test_file_not_found(self):
        """Loading a non-existent file should raise FileNotFoundError."""
        with self.assertRaises(FileNotFoundError):
            load_csv("/nonexistent/path/file.csv", "test")

    def test_loads_valid_csv(self, ):
        """A valid CSV file should load successfully."""
        import tempfile
        import os
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv',
                                         delete=False) as f:
            f.write("name,score\nAlice,10\nBob,20\n")
            tmp_path = f.name
        try:
            result = load_csv(tmp_path, "test")
            self.assertEqual(result.num_rows, 2)
            self.assertEqual(result.num_cols, 2)
            self.assertEqual(result.encoding_used, "utf-8")
        finally:
            os.unlink(tmp_path)

    def test_encoding_fallback(self):
        """A file with Latin-1 encoding should load successfully via fallback."""
        import tempfile, os
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.csv', delete=False) as f:
            f.write("name,city\nAlice,Café\n".encode('latin-1'))
            tmp_path = f.name
        try:
            result = load_csv(tmp_path, "test")
            self.assertEqual(result.encoding_used, "latin-1")
            self.assertIn("latin-1", result.warnings[0])
        finally:
            os.unlink(tmp_path)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main(verbosity=2)