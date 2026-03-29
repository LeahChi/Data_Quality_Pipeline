"""
Empirical comparison of Great Expectations against the initial 3 project datasets. 
Conducted prior to finalising the pipeline architecture.

The purpose of this script:

1. INFORM DESIGN (Chapter 2 — Methodology):
   Run GE on all three datasets with no prior schema knowledge and
   document what it can and cannot detect. Observations from this
   evaluation directly informed design decisions in the custom pipeline,
   particularly the decision to build a schema-agnostic profiler rather
   than extending an existing tool.

2. FORMAL COMPARISON (Chapter 4 — Evaluation):
   After the custom pipeline was built, both tools were run on the same
   datasets and findings compared side by side.

Datasets evaluated:
    - Newcastle Library Loans (data/newcastle_loans.csv)
    - Private Water Supplies (data/private_water.csv)
    - Leeds Market Stalls (data/market_ds.csv)

"""
import great_expectations as gx
import pandas as pd

def run_ge_on_dataset(csv_path: str, dataset_name: str, column_to_check: str) -> None:
    """
    Run a basic Great Expectations validation suite on a single CSV dataset.

    This function intentionally uses only generic expectations that require
    minimal prior knowledge of the dataset — i.e. the same starting
    conditions as the custom pipeline. This is to fairly evaluate what GE
    can detect without a pre-defined schema.

    The function is called once per dataset at the bottom of this script.

    Args:
        csv_path: Path to the CSV file relative to project root.
        dataset_name: Human-readable name used for GE asset naming.
        column_to_check: One column to run null/uniqueness checks on.
                         NOTE: GE requires you to name columns explicitly
                         upfront — you cannot run checks without knowing
                         column names in advance. This is a key limitation
                         compared to the custom pipeline.

    Returns:
        None. Results printed to stdout and noted inline as observations.
    """

    print(f"\n{'='*60}")
    print(f"  {dataset_name}")
    print(f"{'='*60}")

    # Step 1: Load the CSV into a pandas dataframe
    # GE does not load the file itself, you have to do this manually
    # Our pipeline handles this in loader.py.
    df = pd.read_csv(csv_path)
    print(f"Shape: {df.shape}")

    # Step 2: Create a GE context — the central workspace GE needs to operate
    # This creates local config files in a 'gx/' directory automatically.
    # Our pipeline requires no such setup.
    context = gx.get_context()

    # Step 3: Register a pandas data source with GE
    # GE needs to know what kind of data you're connecting to.
    # Our pipeline is format-agnostic.
    ds = context.data_sources.add_pandas(f"pandas_{dataset_name}")

    # Step 4: Add the dataframe as a "data asset"
    # GE treats each dataset as an "asset" that needs to be registered.
    da = ds.add_dataframe_asset(dataset_name)

    # Step 5: Create a batch because GE works on "batches" of data.
    # The whole dataframe is treated as one batch.
    # This is equivalent to my load_csv() returning a LoadResult.
    batch_definition = da.add_batch_definition_whole_dataframe("batch")

    # Step 6: Create an expectation suite: a named collection of rules
    # This is equivalent to our validator.py rule set
    # BUT: GE requires you to define ALL rules manually before running.
    # Our pipeline applies rules automatically based on column types.
    suite = context.suites.add(
        gx.ExpectationSuite(name=f"{dataset_name}_suite")
    )

    # Step 7: Define expectations: the actual checks GE will run
    # OBSERVATION: Every single expectation requires explicit column names and expected values. 
    # GE cannot infer anything about the data without being told. 
    # This means GE is unusable on a dataset one has never seen before without manual configuration.
    expectations = [
        # Check the table has a reasonable number of rows
        # (we have to guess what "reasonable" means — GE cannot infer this)
        gx.expectations.ExpectTableRowCountToBeBetween(
            min_value=1,
            max_value=100000
        ),
        # Check a named column has no null values
        # NOTE: we have to KNOW the column name to do this check
        gx.expectations.ExpectColumnValuesToNotBeNull(
            column=column_to_check
        ),
        # Check a named column has unique values
        # Again — requires knowing the column name upfront
        gx.expectations.ExpectColumnValuesToBeUnique(
            column=column_to_check
        ),
    ]

    # Add each expectation to the suite
    for e in expectations:
        suite.add_expectation(e)

    # Step 8: Create a validation definition and run it
    # This is equivalent to calling validate() in our pipeline
    validation_definition = context.validation_definitions.add(
        gx.ValidationDefinition(
            name=f"{dataset_name}_validation",
            data=batch_definition,
            suite=suite
        )
    )

    # Run the validation and print results
    results = validation_definition.run(batch_parameters={"dataframe": df})
    print(results)

    # OBSERVATION: GE reports pass/fail per expectation but provides no:
    # - Structural missingness classification
    # - Sentinel value detection
    # - Hidden missingness detection (blank strings, encoded nulls)
    # - Automatic type inference
    # - Column-level profiling summary
    # All of these require additional manual configuration in GE.


if __name__ == "__main__":
    # Run GE on all three project datasets
    # The column_to_check parameter highlights a key GE limitation:
    # you must know your column names before you can validate anything.
    # Our pipeline requires zero prior knowledge of column names or types.

    run_ge_on_dataset(
        csv_path="data/newcastle_loans.csv",
        dataset_name="newcastle",
        column_to_check="BranchName"  # known from prior exploration
    )

    run_ge_on_dataset(
        csv_path="data/private_water.csv",
        dataset_name="private_water",
        column_to_check="Postcode"    # known from prior exploration
    )

    run_ge_on_dataset(
        csv_path="data/market_ds.csv",
        dataset_name="market_stalls",
        column_to_check="Date"        # known from prior exploration
    )