"""Sklearn Pipeline construction — all preprocessing INSIDE the pipeline.

WHY PREPROCESSING INSIDE THE PIPELINE PREVENTS LEAKAGE
--------------------------------------------------------
If you fit a StandardScaler on the full dataset before splitting into
train/validation folds, the scaler's mean and std include information from
the validation fold. This inflates reported metrics — the model has
indirectly "seen" the validation data.

Putting the scaler inside Pipeline means sklearn fits it ONLY on the training
portion of each fold during cross-validation. The validation fold sees only
the transform (not the fit). This is the correct, leak-free setup.

FEATURE JUSTIFICATIONS
-----------------------
Kept features and why:

    avg_temp_c        — Climate drives whether a destination is beach/resort
                        (warm) vs. mountain/city (cold). High signal for
                        Relaxation vs. Adventure vs. Culture split.

    cost_per_day_usd  — The single strongest separator. Budget (<$45) vs.
                        Luxury (>$250) is nearly deterministic from this alone.

    safety_index      — Required for Family (high) and differentiates some
                        Budget destinations (safe cheap) from risky ones.

    language_difficulty — Mild signal. Adventure and Budget destinations skew
                          toward harder languages (Asia, Middle East).
                          Family destinations skew toward easy languages
                          (English-speaking countries, Europe).

    activity_density  — Core of the Adventure rule. Also distinguishes Culture
                        (high density, specific activities) from Relaxation
                        (low density, passive).

    nightlife_score   — Distinguishes Culture/Budget city breaks (high nightlife)
                        from Relaxation (moderate) and Family (low).

    cultural_sites    — Key Culture discriminator. Near-zero for Adventure and
                        Relaxation; high for Culture.

    nature_score      — Adventure discriminator. Near-zero for Luxury/Urban;
                        high for Adventure.

    beach_score       — Relaxation discriminator. Near-zero for Culture and Budget;
                        high for Relaxation and some Luxury.

    family_friendly   — Family discriminator. Near-zero for Budget and Adventure;
                        high for Family.

    infrastructure    — Correlates with Luxury (all luxury destinations have
                        10/10 infrastructure) and separates Budget from Culture.

    luxury_index      — The Luxury label separator. Almost no correlation with
                        other labels.

    region (OHE)      — Geographic priors exist: Oceania skews Adventure/Family;
                        Middle East skews Luxury/Culture; Asia is mixed but rich
                        with Budget/Culture.

DROPPED FEATURES and why:

    destination (string) — Unique identifier; would cause 100% overfit if used
                           as a feature.

    country (string)     — ~80 unique values. One-hot encoding on 160 rows would
                           produce ~80 sparse columns, many with 1-2 samples.
                           Would cause severe overfit. Region captures the
                           geographic signal with far fewer columns.

PUBLIC SURFACE
--------------
    NUMERIC_FEATURES: list[str]
    CATEGORICAL_FEATURES: list[str]
    build_preprocessor() -> ColumnTransformer
    build_pipeline(estimator) -> Pipeline
"""

from __future__ import annotations

from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

NUMERIC_FEATURES = [
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
]

CATEGORICAL_FEATURES = ["region"]  # country dropped — see module docstring


def build_preprocessor() -> ColumnTransformer:
    """Build the ColumnTransformer that handles numeric and categorical columns.

    Numeric pipeline:
        SimpleImputer(median) — handles any future NaN without crashing
        StandardScaler        — zero-mean/unit-variance; required for LogReg

    Categorical pipeline:
        SimpleImputer(most_frequent) — defensive; dataset has no NaNs
        OneHotEncoder(handle_unknown="ignore") — 6 regions → 6 binary columns;
            handle_unknown="ignore" means unseen regions get all-zeros at
            inference time rather than raising an error.

    Returns:
        Fitted ColumnTransformer (fit happens inside Pipeline/CV, not here).
    """
    numeric_transformer = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )

    categorical_transformer = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            (
                "onehot",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
            ),
        ]
    )

    return ColumnTransformer(
        transformers=[
            ("num", numeric_transformer, NUMERIC_FEATURES),
            ("cat", categorical_transformer, CATEGORICAL_FEATURES),
        ]
    )


def build_pipeline(estimator: object) -> Pipeline:
    """Wrap a classifier in a full preprocessing + classification pipeline.

    The estimator is parameterised so train.py can swap in LogReg,
    RandomForest, or GradientBoosting without touching the preprocessor.

    Args:
        estimator: Any sklearn-compatible classifier.

    Returns:
        A Pipeline with steps: [preprocess → classifier].

    Usage:
        pipe = build_pipeline(LogisticRegression(...))
        pipe.fit(X_train, y_train)
        pipe.predict(X_test)
    """
    return Pipeline(
        steps=[
            ("preprocess", build_preprocessor()),
            ("classifier", estimator),
        ]
    )
