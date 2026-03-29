# Design Implications

This file maps research findings to concrete pipeline design decisions.
Each entry follows the pattern: **Observation → Decision → Module → Report justification.**

---

## 1. Structural Missingness Classification (Three-Tier System)

**Observation:**
Newcastle Library Loans contains 205 columns. 7 are 100% missing (future time periods not yet recorded), 148 have partial missingness, and 50 are complete. These three groups require fundamentally different treatment — a column that has never had data is not the same as a column with some gaps.

**Decision:**
Implement a three-tier missingness classification:
- `structural` — 100% missing (placeholder columns, not real data gaps)
- `partial` — some values missing (genuine quality issue)
- `complete` — no missing values

**Module:** `profiler.py` — `_classify_missingness()` function

---

## 2. Hidden Missingness Detection (Beyond NaN)

**Observation:**
Private Water Supplies has zero NaN values but still contains data quality issues — a postcode with double whitespace and malformed OS grid references. Simply checking for NaN is insufficient. Additionally, real datasets use various encodings for missing data: blank strings, text sentinels ("n/a", "unknown"), and numeric sentinels (999, -1).

**Decision:**
`missing.py` implements a three-category hidden missingness check:
1. NaN values (standard pandas NA)
2. Blank strings / whitespace-only strings
3. Text sentinel encodings (case-insensitive: "n/a", "unknown", "null", "-", "none")
4. Numeric sentinel detection (flags values like 999, -1, -999, 9999 as warnings)

**Module:** `missing.py` — `detect_missingness()` function

---

## 3. Schema-Agnostic Design (No Prior Configuration Required)

**Observation:**
GE empirical evaluation showed that GE requires explicit column names and expected values before it can check anything. When `BranchName` was passed as the column to check for Newcastle Loans, GE crashed because the exact column name didn't match. A tool that requires schema knowledge cannot work on heterogeneous open datasets.

Wang & Strong (1996) and Abedjan et al. (2015) both assume schema knowledge in their frameworks. Ruddle et al. (2024) Step 1 is the only step that doesn't require domain knowledge.

**Decision:**
Pipeline operates on any CSV file with zero prior configuration. No column names, types, or expected values need to be specified. The pipeline discovers everything automatically.

**Modules:** All, particularly `profiler.py` and `missing.py`

---

## 4. Pluggable Validation Rule Architecture

**Observation:**
Private Water Supplies requires postcode and OS grid reference format validation. Newcastle Loans requires numeric plausibility checks. Market Stalls requires constant column detection. No single fixed set of rules works across all datasets.

However, completely automatic rule inference (without any user input) cannot work for domain-specific formats — the pipeline cannot know that a column named "Postcode" should match UK postcode format without being told.

**Decision:**
`validator.py` implements a **pluggable rule architecture**:
- Built-in rules: `rule_no_negatives`, `rule_no_constant_columns`, `rule_integers_only`
- User-extensible rules: `make_regex_rule()` factory function for custom format checks
- Column-rule mapping passed at runtime via `--column-rules` argument

This preserves schema-agnostic defaults while allowing domain-specific rules to be added when the user has prior knowledge.

**Module:** `validator.py`

---

## 5. Module Separation (Profiling vs Missingness vs Validation)

**Observation:**
Batini et al. (2009) distinguishes between the Measurement phase (profiling) and the Assessment phase (evaluation against requirements). Ruddle et al. Steps 1–4 are also logically distinct activities.

Combining profiling, missingness detection, and validation into one module would make testing harder and outputs less auditable.

**Decision:**
Five separate modules with explicit dataclass contracts:
- `loader.py` → `LoadResult`
- `profiler.py` → `ProfileResult`
- `missing.py` → `MissingnessResult`
- `validator.py` → `ValidationResult`
- `report.py` → HTML + JSON output

Each module takes the output of the previous as input, creating an explicit, testable chain.

**Modules:** All

---

## 6. Dual Output Format (HTML + JSON)

**Observation:**
The pipeline needs to serve two audiences: human analysts (who want readable summaries) and downstream systems (which need structured data). A single output format cannot serve both.

**Decision:**
`report.py` generates two output files per dataset:
- **HTML** — human-readable, styled report with tables and colour-coded classifications
- **JSON** — machine-readable structured output for downstream processing or archiving

**Module:** `report.py`

---

## 7. Scope Narrowing — Step 1 Only (from Steps 1–4)

**Observation:**
Initially the project aimed to automate Steps 1–4 of Ruddle's workflow. Dataset testing revealed that Steps 2–4 require contextual interpretation:
- Step 2: Confirming whether 999 is a sentinel or legitimate value (Cruddas Park) requires domain knowledge.
- Step 3: Determining *why* data is missing requires understanding the data collection process.
- Step 4: Deciding which format validation rules apply (postcode, OS grid ref) requires knowing what the columns represent.

Steps 5–6 (pairs/groups analysis) clearly require domain expertise and were never in scope.

**Decision:**
Scope narrowed to **Step 1 only** — the only step fully automatable without domain knowledge. Steps 2–4 partially inform the pipeline design (the `missing.py` and `validator.py` modules draw on these steps) but are implemented as automated approximations rather than full implementations.


---

## 8. Dataset Selection Criteria

**Decision (from supervisor discussion):**
Dataset selection was restricted to:
- Single-file CSV format
- Metadata available on Data Mill North webpage
- Structural diversity: wide time-series, narrow registry, large mixed-type

This controlled scope reduces confounding factors related to file parsing and metadata availability, allowing the pipeline's behaviour to be evaluated across structurally different datasets.

**Datasets selected:**
- Newcastle Library Loans — wide time-series (19 rows × 205 cols)
- Private Water Supplies — narrow registry (16 rows × 5 cols)
- Leeds Market Stalls — large mixed-type (9,999 rows × 57 cols)

---

## 9. Duplicate Row Detection

**Observation:**
GE empirical evaluation found that postcode `LS14 3HG` appears twice in Private Water Supplies — a finding our pipeline did not make. This is a legitimate data quality issue that a schema-agnostic profiler should detect.

**Decision:**
Add duplicate row detection to the pipeline. `df.duplicated().sum()` — approximately 5 lines of pandas — detects exact duplicate rows and reports count and examples.

**Module:** `profiler.py` (to be added)d