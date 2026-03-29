# Research Observations

## Initial Exploration of Existing Tools

### What I did
- Set up Python development environment.
- Installed and explored Roy Ruddle's `vizdataquality` package.
- Loaded the Leeds Markets dataset from Data Mill North.
- Ran the six-step workflow and generated an HTML data quality report.

### What I observed
- The workflow provides a structured way to inspect datasets.
- Missing values and unique counts immediately highlighted data sparsity.
- Some issues flagged as "problems" were actually explained by dataset metadata.
- The generated report was informative but not easily scalable across many datasets.
- Existing tools are useful for exploration but are not designed for large-scale automated reporting.

---

## Data Mill North Dataset Structure

### What I did
- Explored multiple Data Mill North datasets via the website.
- Noted file formats, metadata availability, and dataset categories.

### What I observed
- Most datasets are CSV or XLSX, but structure varies widely.
- Metadata is inconsistent and sometimes missing or only available as PDFs.
- Some datasets contain summary rows or sparse columns.
- Dataset heterogeneity strongly affects the usefulness of automated checks.
- A controlled dataset selection strategy is necessary for meaningful evaluation.

---

## Newcastle Library Loans — Step 1 (Look at your data)

### What I did
- Loaded the dataset and computed per-column metrics using `vizdataquality`.
- Identified structural all-missing columns.
- Visualised missingness distribution.

### What I observed
- Dataset shape: 19 rows (libraries) × 205 columns (monthly loan counts from 2008 onwards).
- Structure is a wide time-series format: one library per row, one time period per column.
- Columns from 2024-9 onwards contain 100% NaN values — trailing time periods not yet recorded.
- These all-missing columns are classified as float64 because they contain only NaN.
- The Library column has 0 missing values and all values are unique — a stable entity identifier.
- No data type conflicts detected.
- Missingness distribution: 50 columns fully complete, 148 with partial missingness, 7 with 100% missing (structural).
- Plotting all 205 columns was unreadable — summarisation strategies are necessary for wide datasets.

---

## Newcastle Library Loans — Step 2 (Watch out for special values)

### What I did
- Scanned numeric columns for common sentinel encodings (-999, -1, 999, 9999).
- Checked text columns for common placeholder tokens (case-insensitive).

### What I observed
- One occurrence of value `999` detected in column `2011-05` (Cruddas Park library).
- Manual inspection confirmed this represents a plausible loan count, not a placeholder encoding.
- No text-based sentinel encodings found.
- Missing values are consistently encoded as NaN throughout the dataset.

---

## Newcastle Library Loans — Step 3 (Is any data missing?)

### What I did
- Checked residual missingness after structural columns were removed.

### What I observed
- After removing structural all-missing columns, no remaining variables contain missing values.
- All monthly loan counts are complete for retained time periods.

---

## Newcastle Library Loans — Step 4 (Check each variable)

### What I did
- Checked for duplicate library names, negative values, non-integer values, and constant columns.
- Examined max and min values per column.
- Computed monthly loan means to identify temporal anomalies.

### What I observed
- Library identifiers are unique; no duplicates.
- No negative or non-integer values in loan count columns.
- Loan counts range from 0 to 56,618 across the dataset.
- Peak loan activity occurred between 2009–2010.
- Several months in 2020 show extremely low mean loan counts, consistent with COVID-19 operational disruption — not a data error.
- Isolated zero values appear in earlier years, suggesting localised variation rather than systemic error.

---

## Private Water Supplies — Step 1 (Look at your data)

### What I did
- Loaded the dataset and computed per-column metrics.
- Examined structure, completeness, and column-level uniqueness.

### What I observed
- Dataset shape: 16 rows × 5 columns.
- All variables are text-based (object dtype).
- No missing values in any column — fully populated.
- No structural all-missing columns present.
- "Name of Supply" and "OS Grid Ref" are unique across all rows.
- "Source" behaves as a binary variable (Borehole / Spring).
- Dataset is a narrow, record-based registry rather than a wide time-series table.

---

## Private Water Supplies — Step 2 (Watch out for special values)

### What I did
- Checked for blank strings, whitespace-only entries, and text sentinel encodings.

### What I observed
- No numeric columns present — numeric sentinel checks not applicable.
- No blank strings, whitespace-only entries, or common text sentinels detected.
- Missing values appear consistently absent.

---

## Private Water Supplies — Step 3 (Is any data missing?)

### What I did
- Confirmed residual missingness after Steps 1 and 2.

### What I observed
- No missing values present.
- Dataset is fully populated across all records and attributes.

---

## Private Water Supplies — Step 4 (Check each variable)

### What I did
- Validated postcode and OS Grid Reference formats using regex.
- Checked for duplicate records, whitespace inconsistencies, and category consistency.

### What I observed
- No duplicate records.
- One postcode failed regex validation: `LS21  3JL` — double whitespace between district and sector.
- Three OS Grid References failed format validation due to inconsistent spacing and merged digit groups.
- Whitespace inconsistencies detected in "Postcode" and "Type of Water Use e.g. Domestic".
- "Type of Water Use" contains two closely related categories: "Commercial" and "Commercial/Large" — possible semantic inconsistency.
- Key insight: the dataset contains no NaN values but still has real data quality issues.

---

## Great Expectations Empirical Evaluation

### What I did
- Installed GX Core and ran a basic validation suite against all three datasets.
- Used only generic expectations (row count, null check, uniqueness) to simulate schema-agnostic conditions.
- Documented what GE found, what it failed to find, and what the setup process required.

### What I observed

**Newcastle Library Loans:**
- GE crashed trying to validate column `BranchName` — column name did not exist exactly as specified.
- GE requires exact column names upfront — it cannot discover columns automatically.
- Only the row count check passed. GE did not detect structural missingness, sentinel values, or missingness patterns.

**Private Water Supplies:**
- GE confirmed all 16 rows present and Postcode column contains no nulls.
- GE found that postcode `LS14 3HG` appears twice — a duplicate row finding our pipeline missed.
- GE did not detect: postcode spacing error, malformed OS grid refs, or whitespace inconsistencies.

**Leeds Market Stalls:**
- GE confirmed 9,999 rows and found 2 null values in the Date column.
- Our pipeline found 70,519 NaN values total — GE only checked the single column we named.
- GE did not detect: 31 structural columns, constant column, or missingness distribution.

**Overall findings:**
- GE requires prior schema knowledge for every check — fundamentally incompatible with schema-agnostic profiling.
- GE setup requires: context initialisation, data source registration, asset definition, batch definition, and suite creation before any check can run.
- Our pipeline profiles every column automatically with zero configuration.
- GE found one thing our pipeline missed: the duplicate postcode row in Private Water. This motivated adding duplicate detection to the pipeline.