"""Shared pytest fixtures for the ml package."""

from __future__ import annotations

import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression

from src.feature_pipeline import CATEGORICAL_FEATURES, NUMERIC_FEATURES, build_pipeline

# One row per label — minimal but covers all 6 classes.
_ROWS = [
    # dest, country, region, avg_temp_c, cost_per_day_usd, safety_index,
    # language_difficulty, activity_density, nightlife_score, cultural_sites,
    # nature_score, beach_score, family_friendly, infrastructure, luxury_index, label
    ("Queenstown", "New Zealand", "Oceania", 12.0, 80.0, 8, 3, 9, 5, 2, 9, 3, 5, 7, 3, "Adventure"),
    ("Chiang Mai", "Thailand", "Asia", 28.0, 35.0, 7, 6, 6, 5, 5, 5, 2, 5, 6, 2, "Budget"),
    ("Kyoto", "Japan", "Asia", 15.0, 150.0, 9, 8, 7, 2, 9, 4, 1, 7, 8, 5, "Culture"),
    ("Gold Coast", "Australia", "Oceania", 25.0, 130.0, 9, 1, 7, 4, 3, 5, 9, 9, 8, 4, "Family"),
    ("Dubai", "UAE", "Middle East", 32.0, 350.0, 8, 4, 8, 7, 6, 1, 5, 6, 10, 10, "Luxury"),
    ("Maldives", "Maldives", "Asia", 29.0, 400.0, 8, 3, 3, 2, 1, 2, 10, 3, 7, 9, "Relaxation"),
]

_COLUMNS = (
    ["destination", "country"]
    + CATEGORICAL_FEATURES  # ["region"]
    + NUMERIC_FEATURES       # 12 numeric
    + ["label"]
)


@pytest.fixture
def synthetic_df() -> pd.DataFrame:
    """Six-row DataFrame — one sample per label — with all required columns."""
    return pd.DataFrame(_ROWS, columns=["destination", "country"] + CATEGORICAL_FEATURES + NUMERIC_FEATURES + ["label"])


@pytest.fixture
def fitted_pipeline(synthetic_df: pd.DataFrame):
    """Pipeline fitted on the 6-row synthetic dataset."""
    features = NUMERIC_FEATURES + CATEGORICAL_FEATURES
    pipe = build_pipeline(
        LogisticRegression(
            class_weight="balanced",
            max_iter=1000,
            random_state=42,
        )
    )
    pipe.fit(synthetic_df[features], synthetic_df["label"])
    return pipe
