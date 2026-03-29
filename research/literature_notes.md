# Literature Notes

## Wang & Strong (1996) — Beyond Accuracy: What Data Quality Means to Data Consumers
**Source:** JSTOR: https://www.jstor.org/stable/40398176

### Key findings
- Proposed a 15-dimension data quality framework organised into four categories:
  1. **Intrinsic** — accuracy, objectivity, believability, reputation
  2. **Contextual** — relevancy, value-added, timeliness, completeness, appropriate amount of data
  3. **Representational** — interpretability, ease of understanding, concise representation, consistent representation
  4. **Accessibility** — accessibility, access security
- Framework was derived empirically from data consumer perspectives, not theoretical assumptions.
- Data quality is multidimensional — "accuracy" alone is insufficient.

### Implications for my pipeline
- Pipeline scope is limited to **Intrinsic and Representational** categories — these are the only categories that can be assessed without domain knowledge or system access.
- **Contextual** dimensions (relevancy, timeliness, completeness in business sense) require knowing what the data is *for* — a schema-agnostic tool cannot assess these.
- **Accessibility** dimensions require system-level knowledge — out of scope.
- The pipeline directly supports: completeness (missingness detection), consistency (format validation), and interpretability (profiling output).
- This scoping decision is justified in Chapter 2 — the exclusion of Contextual and Accessibility is principled, not arbitrary.

---

## Abedjan, Golab & Naumann (2015) — Profiling Relational Data: A Survey
**Source:** DOI: 10.1007/s00778-015-0389-y

### Key findings
- Data profiling = discovering metadata about a dataset automatically.
- Two main levels: **single-column profiling** (type, cardinality, patterns, statistics) and **multi-column profiling** (dependencies, correlations, keys).
- Single-column profiling is universally applicable; multi-column requires schema assumptions.
- Profiling is the foundation of all subsequent data quality work.

### Implications for my pipeline
- Pipeline implements **single-column profiling only** — consistent with schema-agnostic design.
- Multi-column profiling (e.g., functional dependencies) requires knowing what relationships *should* exist — excluded by design.
- The survey justifies the decision to focus on per-column statistics (type, uniqueness, missingness, value patterns).
- Abedjan's definition of profiling is used as the formal definition in Chapter 1.

---

## Ruddle, Cheshire & Johansson Fernstad (2024) — A Practical Guide to Data Quality and Data Profiling
**Source:** DOI: 10.5518/1481 / https://archive.researchdata.leeds.ac.uk/1235/1/A_practical_guide_to_data_quality_and_data_profiling.pdf

### Key findings
- Proposes a **six-step workflow** for data quality investigation:
  1. Look at your data
  2. Watch out for special values
  3. Is any data missing?
  4. Check each variable
  5. Check pairs of variables
  6. Check groups of records
- Steps 1–4 focus on single-variable and structural issues — broadly automatable.
- Steps 5–6 require understanding relationships between variables — require domain knowledge.
- Step 1 includes specific task codes for profiling activities:
  - **C-1:** Provide example values
  - **C-3:** Count missing values
  - **C-4:** Show missingness distribution
  - **C-7:** Identify data types
  - **C-9:** Count unique values
  - **C-11:** Identify constant columns
  - **C-12:** Detect structural patterns

### Implications for my pipeline
- Pipeline scope is explicitly **Step 1 only** — the only step fully automatable without domain knowledge.
- Steps 2–4 were initially considered but were excluded because they require contextual interpretation:
  - Step 2 (sentinel detection): Can be partially automated, but confirming whether a value is a sentinel or legitimate data requires domain knowledge (e.g., the 999 at Cruddas Park).
  - Step 3 (missingness): Can be detected automatically, but interpreting *why* data is missing is contextual.
  - Step 4 (variable checks): Format rules (postcode, OS grid ref) can be automated, but deciding what rules apply requires prior knowledge.
- Pipeline modules map to Ruddle task codes:
  - `profiler.py` → C-1, C-3, C-4, C-7, C-9, C-11, C-12
  - `missing.py` → C-3, C-4 (extended: blank strings, text sentinels, numeric sentinels)
  - `validator.py` → C-12 (format-level patterns via pluggable rules)
  - `report.py` → all task codes (output)
- Ruddle Step 1 is used as the formal evaluation framework in Chapter 4 (section 4.2.1).

---

## Batini, Cappiello, Francalanci & Maurino (2009) — Methodologies for Data Quality Assessment and Improvement
**Source:** DOI: 10.1145/1541880.1541883

### Key findings
- Proposes a structured methodology for data quality assessment with distinct phases:
  1. **State reconstruction** — understand the data and context
  2. **Measurement** — quantify data quality issues
  3. **Assessment** — evaluate against requirements
  4. **Improvement** — apply corrective actions
- Data quality assessment must be separated from data quality improvement.
- Profiling is the core of the Measurement phase.

### Implications for my pipeline
- Pipeline implements the **Measurement phase only** — consistent with schema-agnostic design.
- The Assessment and Improvement phases require domain requirements — out of scope.
- Batini's phase separation justifies **why `missing.py` is a separate module from `profiler.py`** — profiling and missingness assessment are conceptually distinct phases of measurement.
- The dataclass chain (`LoadResult → ProfileResult → MissingnessResult → ValidationResult`) reflects Batini's structured phase progression.
- This justification is used in the report, Chapter 2 to explain module separation.

---

## Great Expectations (2024) — GX Core Open Source
**Source:** https://greatexpectations.io / https://docs.greatexpectations.io

### Key findings
- GX Core is an open-source Python library for data validation.
- Requires users to define "expectations" — explicit rules about what the data should look like.
- Workflow: connect to data → define expectations → validate → view results.
- Has 300+ built-in expectations covering nulls, ranges, patterns, distributions.
- Used widely in production data pipelines for regression testing.

### Limitations identified empirically
- **Schema-dependent by design** — every expectation requires a named column and expected behaviour.
- Cannot profile unseen data without prior configuration.
- Cannot detect structural missingness automatically.
- Cannot detect sentinel values automatically.
- Cannot detect format inconsistencies without user-defined regex rules.
- Complex setup: requires context initialisation, data source registration, asset definition, batch definition, and suite creation.
- 100+ dependencies installed on setup.

### Implications for my pipeline
- GE represents the primary existing tool comparison
- The fundamental limitation — schema dependency — is the core gap my pipeline fills.
- GE is excellent for known, stable schemas (e.g., production databases with defined contracts).
- GE is unsuitable for heterogeneous open datasets where schema is unknown.
- My pipeline addresses exactly this gap.