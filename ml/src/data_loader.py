"""Load and validate the raw destinations dataset.

PUBLIC SURFACE
--------------
    load_raw(path: str | Path | None = None) -> pd.DataFrame
    compute_dataset_hash(df: pd.DataFrame) -> str
    TARGET_COLUMN: str
    LABEL_CLASSES: list[str]
"""

from __future__ import annotations

import hashlib
import pathlib

import pandas as pd

TARGET_COLUMN = "label"

LABEL_CLASSES = ["Adventure", "Budget", "Culture", "Family", "Luxury", "Relaxation"]

_DEFAULT_PATH = (
    pathlib.Path(__file__).parent.parent / "data" / "raw" / "destinations_raw.csv"
)

# Columns that must be present — checked on load.
_REQUIRED_COLUMNS = {
    "destination",
    "country",
    "region",
    "avg_temp_c",
    "cost_per_day_usd",
    "safety_index",
    "language_difficulty",
    "activity_density",
    "nightlife_score",
    "cultural_sites",
    "nature_score",
    "beach_score",
    "family_friendly",
    "infrastructure",
    "luxury_index",
    "label",
}


def load_raw(path: str | pathlib.Path | None = None) -> pd.DataFrame:
    """Load destinations_raw.csv and run basic sanity checks.

    Args:
        path: Override the default data path.  Useful in tests.

    Returns:
        DataFrame with all columns typed correctly and no nulls.

    Raises:
        FileNotFoundError: If the CSV does not exist.
        ValueError: If required columns are missing or labels are invalid.
    """
    csv_path = pathlib.Path(path) if path else _DEFAULT_PATH

    df = pd.read_csv(csv_path)

    missing = _REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"CSV missing required columns: {missing}")

    if df[TARGET_COLUMN].isnull().any():
        raise ValueError("Dataset contains rows with a null label.")

    unknown_labels = set(df[TARGET_COLUMN].unique()) - set(LABEL_CLASSES)
    if unknown_labels:
        raise ValueError(f"Unknown label values found: {unknown_labels}")

    if df.isnull().any().any():
        raise ValueError("Dataset contains null values — check the CSV.")

    return df


def compute_dataset_hash(df: pd.DataFrame) -> str:
    """SHA-256 hash of the DataFrame content for reproducibility tracking.

    The hash changes whenever any cell value, row order, or column set changes.
    Recorded in results.csv alongside every experiment so a training run can
    be matched to the exact dataset version that produced it.
    """
    content = df.to_csv(index=False).encode("utf-8")
    return hashlib.sha256(content).hexdigest()[:16]
