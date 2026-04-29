"""Compare 3 candidate classifiers + baseline under stratified k-fold CV.

HOW TO RUN
----------
    cd ml/
    uv run python src/train.py

OUTPUT
------
Prints a comparison table to stdout and appends rows to results/results.csv.
The winning model name and params are printed at the end — use them in tune.py.

CLASSIFIERS COMPARED
---------------------
1. DummyClassifier(strategy="stratified")  — the baseline floor
2. LogisticRegression(class_weight="balanced", max_iter=1000)
3. RandomForestClassifier(class_weight="balanced", random_state=42)
4. HistGradientBoostingClassifier(random_state=42)

WHY class_weight="balanced" FOR LOGISTIC REGRESSION AND RANDOM FOREST
----------------------------------------------------------------------
The dataset is near-balanced (25-27 per class), so imbalance is not severe.
We still use class_weight="balanced" as a robustness measure — after a 80/20
train/test split, the smallest class may have only 20 samples, and balanced
weighting ensures the model doesn't implicitly optimise for majority classes.

WHY NOT SMOTE
-------------
SMOTE generates synthetic minority-class samples by interpolating between
existing points. With 160 samples and near-balanced classes, SMOTE would
introduce more noise than signal — interpolated samples in a 12-dimensional
space don't reliably represent real destinations. class_weight="balanced"
achieves imbalance correction without synthetic data.

WHY HistGradientBoosting OVER XGBoost
--------------------------------------
HistGradientBoostingClassifier is sklearn-native, has no external dependency,
handles the dataset size well, and supports native NaN handling. XGBoost is
superior on very large datasets but adds a non-sklearn dependency for marginal
gain at 160 rows.

EVALUATION METHODOLOGY
-----------------------
StratifiedKFold(n_splits=5, shuffle=True, random_state=42) ensures:
    1. Each fold has proportional class representation.
    2. The random split is deterministic — re-running produces identical scores.
Both accuracy AND macro-F1 are reported. Accuracy alone is misleading when
classes are slightly unequal; macro-F1 treats each class equally regardless
of count.
"""

from __future__ import annotations

import csv
import pathlib
from datetime import datetime, timezone
from typing import Any

import numpy as np
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, f1_score
from sklearn.model_selection import StratifiedKFold, cross_val_score

from src.data_loader import LABEL_CLASSES, TARGET_COLUMN, compute_dataset_hash, load_raw
from src.feature_pipeline import (
    CATEGORICAL_FEATURES,
    NUMERIC_FEATURES,
    build_pipeline,
)

RANDOM_STATE = 42
N_SPLITS = 5
RESULTS_CSV = pathlib.Path(__file__).parent.parent / "results" / "results.csv"

CANDIDATES: list[tuple[str, Any]] = [
    (
        "DummyClassifier_stratified",
        DummyClassifier(strategy="stratified", random_state=RANDOM_STATE),
    ),
    (
        "LogisticRegression",
        LogisticRegression(
            class_weight="balanced",
            max_iter=1000,
            random_state=RANDOM_STATE,
        ),
    ),
    (
        "RandomForestClassifier",
        RandomForestClassifier(
            n_estimators=200,
            class_weight="balanced",
            random_state=RANDOM_STATE,
        ),
    ),
    (
        "HistGradientBoostingClassifier",
        HistGradientBoostingClassifier(
            max_iter=200,
            random_state=RANDOM_STATE,
        ),
    ),
]

_RESULTS_HEADER = [
    "timestamp",
    "model",
    "params",
    "dataset_hash",
    "random_state",
    "n_splits",
    "accuracy_mean",
    "accuracy_std",
    "f1_macro_mean",
    "f1_macro_std",
    "f1_Adventure",
    "f1_Budget",
    "f1_Culture",
    "f1_Family",
    "f1_Luxury",
    "f1_Relaxation",
    "features",
    "stage",
]


def _ensure_results_header() -> None:
    """Create results.csv with header row if it doesn't exist."""
    RESULTS_CSV.parent.mkdir(parents=True, exist_ok=True)
    if not RESULTS_CSV.exists():
        with open(RESULTS_CSV, "w", newline="") as f:
            csv.writer(f).writerow(_RESULTS_HEADER)


def _append_result(row: dict[str, Any]) -> None:
    with open(RESULTS_CSV, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_RESULTS_HEADER)
        writer.writerow(row)


def compare_models() -> None:
    """Run the full model comparison and print + persist results."""
    df = load_raw()
    dataset_hash = compute_dataset_hash(df)
    features = NUMERIC_FEATURES + CATEGORICAL_FEATURES

    X = df[features]
    y = df[TARGET_COLUMN]

    cv = StratifiedKFold(n_splits=N_SPLITS, shuffle=True, random_state=RANDOM_STATE)
    _ensure_results_header()

    print(f"\n{'='*70}")
    print(f"Dataset: {len(df)} rows | hash: {dataset_hash} | CV: {N_SPLITS}-fold")
    print(f"Features: {len(features)} ({len(NUMERIC_FEATURES)} numeric, {len(CATEGORICAL_FEATURES)} categorical)")
    print(f"Classes: {LABEL_CLASSES}")
    print(f"{'='*70}\n")

    results = []
    for name, estimator in CANDIDATES:
        pipe = build_pipeline(estimator)

        acc_scores = cross_val_score(pipe, X, y, cv=cv, scoring="accuracy", n_jobs=-1)
        f1_scores = cross_val_score(pipe, X, y, cv=cv, scoring="f1_macro", n_jobs=-1)

        # Per-class F1 — fit on full training set for reporting (not used for model selection).
        from sklearn.model_selection import train_test_split
        X_tr, X_te, y_tr, y_te = train_test_split(
            X, y, test_size=0.2, stratify=y, random_state=RANDOM_STATE
        )
        pipe.fit(X_tr, y_tr)
        y_pred = pipe.predict(X_te)
        per_class_f1 = dict(
            zip(
                LABEL_CLASSES,
                f1_score(y_te, y_pred, labels=LABEL_CLASSES, average=None),
            )
        )

        row = {
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "model": name,
            "params": str(estimator.get_params()),
            "dataset_hash": dataset_hash,
            "random_state": RANDOM_STATE,
            "n_splits": N_SPLITS,
            "accuracy_mean": round(float(acc_scores.mean()), 4),
            "accuracy_std": round(float(acc_scores.std()), 4),
            "f1_macro_mean": round(float(f1_scores.mean()), 4),
            "f1_macro_std": round(float(f1_scores.std()), 4),
            **{f"f1_{k}": round(v, 4) for k, v in per_class_f1.items()},
            "features": "|".join(features),
            "stage": "comparison",
        }
        _append_result(row)
        results.append((name, row))

        print(f"[{name}]")
        print(f"  Accuracy: {acc_scores.mean():.4f} ± {acc_scores.std():.4f}")
        print(f"  F1-macro: {f1_scores.mean():.4f} ± {f1_scores.std():.4f}")
        print(f"  Per-class F1 (held-out 20%):")
        for label, score in per_class_f1.items():
            print(f"    {label:12s}: {score:.4f}")
        print()

    # Identify winner (exclude baseline from winner selection)
    non_baseline = [(n, r) for n, r in results if "Dummy" not in n]
    winner_name, winner_row = max(non_baseline, key=lambda x: x[1]["f1_macro_mean"])

    print(f"{'='*70}")
    print(f"WINNER: {winner_name}")
    print(f"  F1-macro CV: {winner_row['f1_macro_mean']:.4f} ± {winner_row['f1_macro_std']:.4f}")
    print(f"  Accuracy CV: {winner_row['accuracy_mean']:.4f} ± {winner_row['accuracy_std']:.4f}")
    print(f"{'='*70}")
    print(f"\nNext step: run  uv run python src/tune.py  to tune {winner_name}")


if __name__ == "__main__":
    compare_models()
