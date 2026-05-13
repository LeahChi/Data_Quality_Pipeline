"""
run_pipeline.py — Entry point for the data quality profiling pipeline.

Usage:
    python run_pipeline.py --input data/newcastle_loans.csv --name "Newcastle Library Loans"
    python run_pipeline.py --input data/private_water.csv --name "Private Water Supplies"
    python run_pipeline.py --input data/market_ds.csv --name "Leeds Market Stalls"

With format validation rules:
    python run_pipeline.py --input data/private_water.csv \\
        --name "Private Water Supplies" \\
        --column-rules "Postcode:valid_postcode" "OS Grid Ref:valid_os_grid_ref"
"""

import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from pipeline.loader import load_csv
from pipeline.profiler import profile
from pipeline.missing import detect_missingness
from pipeline.validator import validate
from pipeline.validator import rule_valid_postcode, rule_valid_os_grid_ref
from pipeline.report import generate_report


RULE_REGISTRY = {
    "valid_postcode": rule_valid_postcode,
    "valid_os_grid_ref": rule_valid_os_grid_ref,
}


def parse_args():
    p = argparse.ArgumentParser(description="Data Quality Profiling Pipeline")
    p.add_argument("--input", required=True, help="Path to input CSV")
    p.add_argument("--name", default=None, help="Dataset display name")
    p.add_argument("--output", default="outputs", help="Output directory")
    p.add_argument(
        "--column-rules", nargs="*", default=[],
        help="Column-specific rules as 'ColumnName:rule_name' pairs"
    )
    return p.parse_args()


def main():
    args = parse_args()

    print(f"\n{'='*60}")
    print(f"  Data Quality Profiling Pipeline")
    print(f"{'='*60}")

    print(f"\n[1/4] Loading: {args.input}")
    
    try:
        load_result = load_csv(args.input, dataset_name=args.name)
    except ValueError as e:
        print(f"\n[ERROR] {e}")
        print("Pipeline halted — please provide a valid CSV file.")
        sys.exit(1)

    print(f"      {load_result.num_rows:,} rows x {load_result.num_cols} columns")
    print(f"      Encoding: {load_result.encoding_used}")
    for w in load_result.warnings:
        print(f"      WARNING: {w}")

    print(f"\n[2/4] Profiling...")
    profiling_result = profile(load_result)
    print(f"      Structural (100% missing) : {len(profiling_result.structural_cols)}")
    print(f"      Partial missingness       : {len(profiling_result.partial_cols)}")
    print(f"      Fully complete            : {len(profiling_result.complete_cols)}")

    print(f"\n[3/4] Detecting missingness...")
    missingness_result = detect_missingness(load_result.df, profiling_result)
    s = missingness_result.summary
    print(f"      NaN values            : {s['total_nan_values']:,}")
    print(f"      Blank strings         : {s['total_blank_string_values']}")
    print(f"      Text sentinels        : {s['total_text_sentinel_values']}")
    print(f"      Numeric sentinel cols : {s['numeric_sentinel_flagged_cols']}")

    print(f"\n[4/4] Validating...")
    column_rules = {}
    for spec in args.column_rules:
        if ":" not in spec:
            continue
        col, rule_name = spec.split(":", 1)
        if rule_name in RULE_REGISTRY:
            column_rules.setdefault(col, []).append(RULE_REGISTRY[rule_name])

    validation_result = validate(
        load_result.df, profiling_result, text_rules=column_rules
    )
    print(f"      Errors   : {validation_result.error_count}")
    print(f"      Warnings : {validation_result.warning_count}")
    for issue in validation_result.issues[:5]:
        marker = "x" if issue.severity == "error" else "!"
        print(f"      {marker} [{issue.column}] {issue.message}")
    if len(validation_result.issues) > 5:
        print(f"      ... and {len(validation_result.issues)-5} more (see report)")

    outputs = generate_report(
        profiling_result, missingness_result, validation_result,
        output_dir=args.output, df = load_result.df)

    print(f"\n{'='*60}")
    print(f"  Reports generated:")
    for fmt, path in outputs.items():
        print(f"    {fmt.upper()} -> {path}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
