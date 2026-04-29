"""Tests for the persisted joblib artifact and results.csv."""

from __future__ import annotations

import csv
import pathlib

import joblib
import pytest

from src.data_loader import LABEL_CLASSES, load_raw
from src.feature_pipeline import CATEGORICAL_FEATURES, NUMERIC_FEATURES

_MODELS_DIR = pathlib.Path(__file__).parent.parent / "models"
_RESULTS_CSV = pathlib.Path(__file__).parent.parent / "results" / "results.csv"


@pytest.fixture
def classifier():
    """Load the most recently saved joblib artifact."""
    artifacts = sorted(_MODELS_DIR.glob("travel_style_classifier_v*.joblib"))
    if not artifacts:
        pytest.skip("No joblib artifact found — run tune.py first.")
    return joblib.load(artifacts[-1])


class TestJoblib:
    def test_artifact_exists(self) -> None:
        artifacts = list(_MODELS_DIR.glob("travel_style_classifier_v*.joblib"))
        assert artifacts, "No model artifact found in ml/models/"

    def test_loads_without_error(self, classifier) -> None:
        assert classifier is not None

    def test_predicts_known_label(self, classifier) -> None:
        df = load_raw()
        features = NUMERIC_FEATURES + CATEGORICAL_FEATURES
        preds = classifier.predict(df[features].head(10))
        assert set(preds).issubset(set(LABEL_CLASSES))

    def test_prediction_is_deterministic(self, classifier) -> None:
        """Same input must produce the same output across calls."""
        df = load_raw()
        features = NUMERIC_FEATURES + CATEGORICAL_FEATURES
        X = df[features].head(20)
        preds1 = classifier.predict(X)
        preds2 = classifier.predict(X)
        assert list(preds1) == list(preds2)

    def test_predict_proba_sums_to_one(self, classifier) -> None:
        import numpy as np

        df = load_raw()
        features = NUMERIC_FEATURES + CATEGORICAL_FEATURES
        proba = classifier.predict_proba(df[features].head(10))
        assert all(abs(row.sum() - 1.0) < 1e-6 for row in proba)

    def test_all_classes_in_classifier(self, classifier) -> None:
        """The fitted classifier must know about all 6 travel-style labels."""
        classes = list(classifier.classes_)
        assert sorted(classes) == sorted(LABEL_CLASSES)


class TestResultsCSV:
    def test_results_csv_exists(self) -> None:
        assert _RESULTS_CSV.exists(), "results/results.csv not found"

    def test_has_at_least_one_row(self) -> None:
        with open(_RESULTS_CSV, newline="") as f:
            rows = list(csv.DictReader(f))
        assert rows, "results.csv has no data rows"

    def test_tuning_row_present(self) -> None:
        with open(_RESULTS_CSV, newline="") as f:
            rows = list(csv.DictReader(f))
        stages = [r.get("stage", "") for r in rows]
        assert "tuning" in stages, "No tuning row found in results.csv"

    def test_comparison_rows_present(self) -> None:
        with open(_RESULTS_CSV, newline="") as f:
            rows = list(csv.DictReader(f))
        stages = [r.get("stage", "") for r in rows]
        assert "comparison" in stages, "No comparison rows found in results.csv"

    def test_dataset_hash_recorded(self) -> None:
        with open(_RESULTS_CSV, newline="") as f:
            rows = list(csv.DictReader(f))
        assert all(len(r.get("dataset_hash", "")) == 16 for r in rows)
