"""Save the winning model artifact and append a row to results/results.csv.

PUBLIC SURFACE
--------------
    persist_model(
        fitted_pipeline,
        *,
        model_name,
        best_params,
        cv_f1_macro,
        test_eval,
        dataset_hash,
    ) -> pathlib.Path

HOW VERSION BUMPING WORKS
--------------------------
The function scans ml/models/ for existing files matching
    travel_style_classifier_v<n>.joblib
and picks n = max_existing + 1.  This means re-running tune.py never
overwrites the previous artifact — useful when comparing tuning runs.

CSV SCHEMA
----------
Appends to the same results/results.csv used by train.py.  The schema is
the superset of both comparison and tuning columns; fields unused by each
stage are written as empty strings so the file stays valid for DictReader.
"""

from __future__ import annotations

import csv
import pathlib
from datetime import datetime, timezone
from typing import Any

import joblib

_MODELS_DIR = pathlib.Path(__file__).parent.parent / "models"
_RESULTS_CSV = pathlib.Path(__file__).parent.parent / "results" / "results.csv"

# Shared with train.py — both scripts append rows to the same file.
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


def _next_version() -> int:
    """Return the next version number by scanning existing model files."""
    _MODELS_DIR.mkdir(parents=True, exist_ok=True)
    existing = list(_MODELS_DIR.glob("travel_style_classifier_v*.joblib"))
    if not existing:
        return 1
    versions = []
    for p in existing:
        stem = p.stem  # e.g. "travel_style_classifier_v3"
        try:
            versions.append(int(stem.split("_v")[-1]))
        except ValueError:
            pass
    return max(versions, default=0) + 1


def _ensure_results_header() -> None:
    _RESULTS_CSV.parent.mkdir(parents=True, exist_ok=True)
    if not _RESULTS_CSV.exists():
        with open(_RESULTS_CSV, "w", newline="") as f:
            csv.writer(f).writerow(_RESULTS_HEADER)


def persist_model(
    fitted_pipeline: Any,
    *,
    model_name: str,
    best_params: dict[str, Any],
    cv_f1_macro: float,
    test_eval: dict[str, Any],
    dataset_hash: str,
    random_state: int = 42,
) -> pathlib.Path:
    """Dump the fitted pipeline to disk and record metrics in results.csv.

    Args:
        fitted_pipeline: A fitted sklearn Pipeline ready for inference.
        model_name: Human-readable model name (e.g. "LogisticRegression").
        best_params: Dict of best hyperparameters from GridSearchCV.
        cv_f1_macro: Best cross-validation macro-F1 score from GridSearchCV.
        test_eval: Dict returned by evaluate_on_holdout() with keys:
            accuracy, f1_macro, baseline_accuracy, per_class_f1.
        dataset_hash: SHA-256 prefix of the training dataset (from
            compute_dataset_hash()) — links the artifact to the exact data.
        random_state: Random seed used throughout training (default 42).

    Returns:
        Path to the saved .joblib file.
    """
    version = _next_version()
    out_path = _MODELS_DIR / f"travel_style_classifier_v{version}.joblib"
    joblib.dump(fitted_pipeline, out_path)

    per_class: dict[str, float] = test_eval.get("per_class_f1", {})

    _ensure_results_header()
    row: dict[str, Any] = {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "model": model_name,
        "params": str(best_params),
        "dataset_hash": dataset_hash,
        "random_state": random_state,
        "n_splits": "",
        "accuracy_mean": round(test_eval.get("accuracy", 0.0), 4),
        "accuracy_std": "",
        "f1_macro_mean": round(cv_f1_macro, 4),
        "f1_macro_std": "",
        "f1_Adventure": round(per_class.get("Adventure", 0.0), 4),
        "f1_Budget": round(per_class.get("Budget", 0.0), 4),
        "f1_Culture": round(per_class.get("Culture", 0.0), 4),
        "f1_Family": round(per_class.get("Family", 0.0), 4),
        "f1_Luxury": round(per_class.get("Luxury", 0.0), 4),
        "f1_Relaxation": round(per_class.get("Relaxation", 0.0), 4),
        "features": "",
        "stage": "tuning",
    }
    with open(_RESULTS_CSV, "a", newline="") as f:
        csv.DictWriter(f, fieldnames=_RESULTS_HEADER).writerow(row)

    return out_path
