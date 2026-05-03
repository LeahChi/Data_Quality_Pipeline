"""
loader.py - Type-aware dataset ingestion module.

This is the entry point for the pipeline. Its sole responsibility is
to load any CSV file and capture structural metadata about it. 
No decisions are made here about data quality, that is deferred
to profiler.py and beyond.

Design rationale:
    Exploratory analysis on the Newcastle Library Loans dataset revealed
    that wide time-series CSVs contain trailing all-NaN columns that are
    inferred as float64 by pandas. A naive load would misrepresent the
    true dataset structure. This module makes the loading step explicit
    and auditable.

    Abedjan et al. (2015) identify dataset ingestion and type inference
    as the foundational step of any profiling pipeline. This module
    implements that foundation without making assumptions about structure,
    schema, or domain.
"""

import pandas as pd
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LoadResult:
    """
    Structured output from a load operation:

    Rather than returning a bare DataFrame, we return this dataclass so
    that every following module has access to ingestion-time metadata
    (shape, dtypes, encoding, warnings) alongside the data itself.
    This makes the pipeline auditable — you can always trace back to
    what the loader saw.
    """
    df: pd.DataFrame    # the loaded DataFrame
    dataset_name: str   # human-readable name (used in reports)
    source_path: str
    num_rows: int
    num_cols: int
    column_names: list  # list of column names in original order
    dtypes: dict        # mapping of column name to inferred dtype (as string)
    encoding_used: str  # encoding that successfully loaded the file for example "utf-8" or "latin-1"
    warnings: list = field(default_factory=list)
    # Stores any issues encountered during loading, e.g. encoding fallback.
    # field(default_factory=list): each LoadResult instance gets its own independent list -  
    # so that warnings from one dataset don't bleed into another.



def load_csv(
    filepath: str,
    dataset_name: Optional[str] = None,
    encoding: str = "utf-8",
    fallback_encoding: str = "latin-1",
) -> LoadResult:
    """
    Load a CSV file into a pandas DataFrame with encoding fallback.

    Args:
        filepath: Path to the CSV file.
        dataset_name: Human-readable name for the dataset (defaults to filename).
        encoding: Primary encoding to attempt (default: utf-8).
        fallback_encoding: Encoding to use if primary fails (default: latin-1).

    Returns:
        LoadResult dataclass containing the DataFrame and structural metadata.

    Raises:
        FileNotFoundError: If the specified file does not exist.
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Dataset file not found: {filepath}")

    name = dataset_name or path.stem  # .stem gives you the filename without its extension
    warnings = []
    encoding_used = encoding

    try:
        df = pd.read_csv(path, encoding=encoding)
    except UnicodeDecodeError:
        df = pd.read_csv(path, encoding=fallback_encoding)
        encoding_used = fallback_encoding
        warnings.append(
            f"Primary encoding '{encoding}' failed; loaded with '{fallback_encoding}'."
        )
    except pd.errors.EmptyDataError:
        raise ValueError(
            f"Dataset file is empty and contains no columns: {filepath}"
        )

    if df.empty and len(df.columns) == 0:
        raise ValueError(
            f"Dataset file contains no columns: {filepath}"
        )

    return LoadResult(
        df=df,
        dataset_name=name,
        source_path=str(path.resolve()), # absolute path for traceability
        num_rows=df.shape[0],
        num_cols=df.shape[1],
        column_names=df.columns.tolist(),
        dtypes={col: str(df[col].dtype) for col in df.columns},
        encoding_used=encoding_used,
        warnings=warnings,
    )


