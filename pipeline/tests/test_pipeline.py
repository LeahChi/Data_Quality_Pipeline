"""
tests/test_pipeline.py - Unit tests for the data quality profiling pipeline.

Tests cover the core logic of each module independently, using synthetic
DataFrames to avoid dependency on external data files.
"""

import sys
import os
import unittest
import json
import tempfile
import pandas as pd
import numpy as np

# Ensure pipeline modules are importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from profiler import profile, _classify_missingness, _check_numeric_sentinels, _check_text_sentinels
from validator import validate, rule_no_negatives, rule_no_constant_columns, rule_integers_only, make_regex_rule
from reporter import to_json, to_html
from loader import LoadResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_load_result(df: pd.DataFrame, name: str = "test_dataset") -> LoadResult:
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
# profiler tests
# ---------------------------------------------------------------------------

class TestClassifyMissingness:
    def test_structural(self):
        assert _classify_missingness(1.0) == "structural"

    def test_complete(self):
        assert _classify_missingness(0.0) == "complete"

    def test_partial(self):
        assert _classify_missingness(0.5) == "partial"


class TestNumericSentinels:
    def test_detects_known_sentinel(self):
        s = pd.Series([1, 2, -999, 4])
        flags = _check_numeric_sentinels(s)
        assert any(f["value"] == -999 for f in flags)

    def test_no_false_positive(self):
        s = pd.Series([10, 20, 30, 40])
        flags = _check_numeric_sentinels(s)
        assert flags == []


class TestTextSentinels:
    def test_detects_na_string(self):
        s = pd.Series(["Leeds", "n/a", "Bradford"])
        flags = _check_text_sentinels(s)
        assert any(f["value"] == "n/a" for f in flags)

    def test_case_insensitive(self):
        s = pd.Series(["Unknown", "Sheffield"])
        flags = _check_text_sentinels(s)
        assert any(f["value"] == "unknown" for f in flags)

    def test_no_false_positive(self):
        s = pd.Series(["Leeds", "Bradford", "York"])
        flags = _check_text_sentinels(s)
        assert flags == []


class TestProfile:
    def test_structural_col_detected(self):
        df = pd.DataFrame({
            "id": [1, 2, 3],
            "empty": [np.nan, np.nan, np.nan],
        })
        result = profile(make_load_result(df))
        assert "empty" in result.structural_cols

    def test_complete_col_classified(self):
        df = pd.DataFrame({"name": ["Alice", "Bob", "Carol"]})
        result = profile(make_load_result(df))
        assert "name" in result.complete_cols

    def test_partial_col_classified(self):
        df = pd.DataFrame({"score": [1.0, np.nan, 3.0]})
        result = profile(make_load_result(df))
        assert "score" in result.partial_cols

    def test_constant_col_flagged(self):
        df = pd.DataFrame({"status": ["active", "active", "active"]})
        result = profile(make_load_result(df))
        col_profile = next(p for p in result.column_profiles if p.name == "status")
        assert col_profile.is_constant is True


# ---------------------------------------------------------------------------
# validator tests
# ---------------------------------------------------------------------------

class TestRuleNoNegatives:
    def test_flags_negatives(self):
        s = pd.Series([1, -5, 3])
        issue = rule_no_negatives(s, "count")
        assert issue is not None
        assert issue.affected_count == 1

    def test_passes_clean(self):
        s = pd.Series([1, 2, 3])
        assert rule_no_negatives(s, "count") is None


class TestRuleNoConstantColumns:
    def test_flags_constant(self):
        s = pd.Series([7, 7, 7])
        issue = rule_no_constant_columns(s, "col")
        assert issue is not None

    def test_passes_varied(self):
        s = pd.Series([1, 2, 3])
        assert rule_no_constant_columns(s, "col") is None


class TestRuleIntegersOnly:
    def test_flags_floats(self):
        s = pd.Series([1.0, 2.5, 3.0])
        issue = rule_integers_only(s, "count")
        assert issue is not None
        assert issue.affected_count == 1

    def test_passes_whole_numbers(self):
        s = pd.Series([1.0, 2.0, 3.0])
        assert rule_integers_only(s, "count") is None


class TestRegexRule:
    def test_postcode_valid(self):
        rule = make_regex_rule(r"^[A-Z]{1,2}[0-9][0-9A-Z]?\s?[0-9][A-Z]{2}$", "postcode", "UK postcode")
        s = pd.Series(["LS1 4AP", "BD1 1AA"])
        assert rule(s, "postcode") is None

    def test_postcode_invalid(self):
        rule = make_regex_rule(r"^[A-Z]{1,2}[0-9][0-9A-Z]?\s?[0-9][A-Z]{2}$", "postcode", "UK postcode")
        s = pd.Series(["LS1 4AP", "INVALID"])
        issue = rule(s, "postcode")
        assert issue is not None
        assert issue.affected_count == 1


class TestValidate:
    def test_returns_issues_for_negatives(self):
        df = pd.DataFrame({"loans": [10, -1, 5]})
        lr = make_load_result(df)
        from profiler import profile
        pr = profile(lr)
        vr = validate(df, pr)
        assert any(i.rule_name == "no_negatives" for i in vr.issues)

    def test_structural_cols_excluded(self):
        df = pd.DataFrame({
            "loans": [1, 2, 3],
            "empty": [np.nan, np.nan, np.nan],
        })
        lr = make_load_result(df)
        from profiler import profile
        pr = profile(lr)
        vr = validate(df, pr, exclude_structural=True)
        # No issues should reference the empty column
        assert not any(i.column == "empty" for i in vr.issues)


# ---------------------------------------------------------------------------
# reporter tests
# ---------------------------------------------------------------------------

class TestReporter:
    def setup_method(self):
        df = pd.DataFrame({
            "id": [1, 2, 3],
            "value": [10.0, np.nan, 30.0],
        })
        lr = make_load_result(df)
        from profiler import profile
        from validator import validate
        self.pr = profile(lr)
        self.vr = validate(df, self.pr)

    def test_json_output_created(self, tmp_path):
        out = str(tmp_path / "report.json")
        result = to_json(self.pr, self.vr, out)
        import json, os
        assert os.path.exists(result)
        with open(result) as f:
            data = json.load(f)
        assert data["dataset"] == "test_dataset"
        assert "profile" in data
        assert "validation" in data

    def test_html_output_created(self, tmp_path):
        out = str(tmp_path / "report.html")
        result = to_html(self.pr, self.vr, out)
        import os
        assert os.path.exists(result)
        with open(result) as f:
            content = f.read()
        assert "test_dataset" in content
        assert "<table>" in content


if __name__ == "__main__":
    unittest.main(verbosity=2)
