"""Held-out test-set evaluation utilities.

PUBLIC SURFACE
--------------
    evaluate_on_holdout(
        fitted_pipeline, X_test, y_test, baseline, label_classes
    ) -> dict[str, float | dict]

Called by both train.py (for per-class reporting) and tune.py (after
GridSearchCV picks the best estimator).  Returns a flat dict so callers
can log it, persist it to results.csv, or print individual fields without
importing sklearn directly.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.metrics import accuracy_score, f1_score


def evaluate_on_holdout(
    fitted_pipeline: Any,
    X_test: Any,
    y_test: Any,
    baseline: Any,
    label_classes: list[str],
) -> dict[str, Any]:
    """Compute accuracy, macro-F1, per-class F1, and baseline accuracy.

    Args:
        fitted_pipeline: An already-fitted sklearn Pipeline (or any estimator
            with a .predict() method).
        X_test: Feature matrix for the held-out test set.
        y_test: True labels for the held-out test set.
        baseline: An already-fitted DummyClassifier (or equivalent) used to
            compute the baseline accuracy floor.
        label_classes: Ordered list of class names matching LABEL_CLASSES in
            data_loader.py — used to align per-class F1 scores.

    Returns:
        Dict with keys:
            accuracy          — float, test-set accuracy of the main pipeline
            f1_macro          — float, macro-averaged F1 across all classes
            baseline_accuracy — float, DummyClassifier accuracy on same test set
            per_class_f1      — dict[str, float] mapping class name → F1 score
    """
    y_pred = fitted_pipeline.predict(X_test)
    y_baseline = baseline.predict(X_test)

    per_class_f1_values: np.ndarray = f1_score(
        y_test,
        y_pred,
        labels=label_classes,
        average=None,
        zero_division=0,
    )

    return {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "f1_macro": float(
            f1_score(y_test, y_pred, average="macro", zero_division=0)
        ),
        "baseline_accuracy": float(accuracy_score(y_test, y_baseline)),
        "per_class_f1": dict(zip(label_classes, per_class_f1_values.tolist())),
    }
